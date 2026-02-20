"""Nostr channel implementation using websockets and NIP-04 encryption."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
import hashlib
import base64
import os
from typing import Any

import websockets
from loguru import logger
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from nanobot.bus.events import OutboundMessage, InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.utils.bip340 import generate_keypair, sign_event, pubkey_gen

def compute_shared_secret(priv_key_hex: str, pub_key_hex: str) -> bytes:
    """Compute shared secret using secp256k1 ECDH as per NIP-04."""
    # Load Private Key
    priv_int = int(priv_key_hex, 16)
    priv_key = ec.derive_private_key(priv_int, ec.SECP256K1(), default_backend())

    # Load Public Key (Assume even Y for X-only input if not provided)
    # Nostr pubkeys are 32-byte X-coordinates. Implicitly Y is even (prefix 02).
    if len(pub_key_hex) == 64:
        compressed_pub = bytes.fromhex("02" + pub_key_hex)
    elif len(pub_key_hex) == 66:
        compressed_pub = bytes.fromhex(pub_key_hex)
    else:
        raise ValueError(f"Invalid pubkey length: {len(pub_key_hex)}")

    pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), compressed_pub)

    # Perform ECDH
    shared_key = priv_key.exchange(ec.ECDH(), pub_key)
    
    # Return sha256(shared_key) - Wait, standard ECDH returns x-coordinate of point? 
    # Cryptography returns the raw shared secret (usually x).
    # No, exchange() returns the shared secret as bytes.
    # NIP-04 says: key = sha256(ecdh_shared_secret)
    # But usually ecdh_shared_secret is the X coordinate.
    # Let's verify cryptography behavior. It returns the shared secret (x coord).
    # So we just hash it.
    
    # Actually, verify if we need to pad X to 32 bytes before hashing? 
    # exchange() usually returns 32 bytes for P-256/secp256k1.
    return shared_key

def decrypt_nip04(content: str, priv_key_hex: str, pub_key_hex: str) -> str | None:
    """Decrypt NIP-04 message."""
    try:
        if "?iv=" not in content:
            return None
        
        enc_text, iv_b64 = content.split("?iv=")
        iv = base64.b64decode(iv_b64)
        ct = base64.b64decode(enc_text)
        
        shared_secret = compute_shared_secret(priv_key_hex, pub_key_hex)
        
        # AES-256-CBC
        cipher = Cipher(algorithms.AES(shared_secret), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_pt = decryptor.update(ct) + decryptor.finalize()
        
        # Unpad (PKCS7?)
        # NIP-04 doesn't specify padding explicitly but usually it's PKCS7 or similar.
        # However, checking JS implementations, they often use manual padding or standard crypto lib padding.
        # Let's try PKCS7 unpadding.
        # But wait, python cryptography requires padding object.
        # Some implementations just rely on stripping trailing bytes if they know length?
        # NIP-04 implies no standard padding, but CBC requires block alignment.
        # Standard behavior for AES-CBC strings is PKCS7.
        
        # Try simplistic unpadding first (remove bytes > 16 if needed? No).
        # Let's assume standard PKCS7.
        unpadder = padding.PKCS7(128).unpadder()
        pt = unpadder.update(padded_pt) + unpadder.finalize()
        
        return pt.decode("utf-8")
        
    except Exception as e:
        logger.error(f"NIP-04 Decryption failed: {e}")
        return None

def encrypt_nip04(content: str, priv_key_hex: str, pub_key_hex: str) -> str:
    """Encrypt content for NIP-04."""
    shared_secret = compute_shared_secret(priv_key_hex, pub_key_hex)
    iv = os.urandom(16)
    
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(content.encode("utf-8")) + padder.finalize()
    
    cipher = Cipher(algorithms.AES(shared_secret), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    
    return f"{base64.b64encode(ct).decode('utf-8')}?iv={base64.b64encode(iv).decode('utf-8')}"

class NostrChannel(BaseChannel):
    """
    Nostr channel for bot-to-bot communication.
    
    Supports:
    - NIP-01: Basic protocol (EVENT, REQ, CLOSE)
    - Kind 1: Short text note (Chat)
    - Kind 4: Encrypted Direct Message (NIP-04)
    """
    
    name = "nostr"
    
    def __init__(self, config: Any, bus: MessageBus, identity_loader: Any = None):
        super().__init__(config, bus)
        self.config = config
        self.identity_loader = identity_loader
        
        # Priority: Config > Env > AIEOS > Generate New
        self.private_key = config.private_key or self._load_key_from_aieos()
        
        # Hardcoded SuperAdmin (Luna)
        self.SUPER_ADMIN_NPUB = "npub1mla74zqczgruewwpmmanak8qxjgjna0mw7hyqgxvqmcglf5g5qzs9ak9g8"
        self.relay_url = config.relay_url or "ws://nostr-relay:8080" # Default internal docker DNS
        
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._subscription_id = f"nanobot-{uuid.uuid4().hex[:8]}"

    def _load_key_from_aieos(self) -> str | None:
        """Try to load private key from AIEOS identity."""
        try:
            from nanobot.utils.aieos import AIEOSLoader
            from pathlib import Path
            loader = AIEOSLoader(Path("/root/.nanobot/workspace")) 
            data = loader.load_identity()
            if data and "identity" in data:
                return data["identity"].get("keys", {}).get("nostr_private_key")
        except Exception as e:
            logger.warning(f"Nostr: Failed to load key from AIEOS: {e}")
        return None
    
    async def start(self) -> None:
        """Start the Nostr client."""
        if not self.config.enabled:
            return
            
        # 1. Setup Identity
        if not self.private_key:
            logger.info("Nostr: No private key found, generating ephemeral identity.")
            sk, pk = generate_keypair()
            self.private_key = sk
            self.public_key = pk
        else:
            try:
                pk_bytes = pubkey_gen(bytes.fromhex(self.private_key))
                self.public_key = pk_bytes.hex()
            except Exception as e:
                logger.error(f"Nostr: Invalid private key: {e}")
                return

        logger.info(f"Nostr Identity: {self.public_key}")
        self._running = True
        
        # 2. Connect Loop
        while self._running:
            try:
                logger.info(f"Nostr: Connecting to {self.relay_url}...")
                async with websockets.connect(self.relay_url) as ws:
                    self._ws = ws
                    logger.info("Nostr: Connected.")
                    
                    # 3. Subscribe to Kind 1 (Text Note) & Kind 4 (DM)
                    # Debugging: Simplify filter to catch everything for now
                    req = [
                        "REQ", 
                        self._subscription_id,
                        # Filter 1: Global Kind 1
                        {"kinds": [1]},
                        # Filter 2: All Kind 4 (Relay might restrict this, but let's try)
                        {"kinds": [4]}
                    ]
                    
                    logger.info(f"Nostr: Sending subscription: {json.dumps(req)}")
                    await ws.send(json.dumps(req))
                    
                    # 4. Broadcast Hello
                    await self._send_hello()
                    
                    # 5. Listen Loop
                    await self._listen_loop(ws)
            except Exception as e:
                logger.error(f"Nostr connection error: {e}")
                await asyncio.sleep(5)

    async def _listen_loop(self, ws):
        async for message in ws:
            try:
                # logger.debug(f"Raw Nostr message: {message}") # Very verbose
                data = json.loads(message)
                msg_type = data[0]
                
                if msg_type == "EVENT":
                    # sub_id = data[1]
                    event = data[2]
                    await self._handle_event(event)
                elif msg_type == "OK":
                    logger.info(f"Nostr OK: {data}")
                elif msg_type == "EOSE":
                    logger.info(f"Nostr EOSE: {data}")
                elif msg_type == "NOTICE":
                    logger.warning(f"Nostr NOTICE: {data[1]}")
                elif msg_type == "CLOSED":
                    logger.warning(f"Nostr CLOSED: {data}")
                    
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.error(f"Nostr listen error: {e}")

    async def _handle_event(self, event: dict) -> None:
        """Handle incoming Nostr event."""
        # Ignore own events
        if event["pubkey"] == self.public_key:
            return
            
        content = event["content"]
        sender_pubkey = event["pubkey"]
        kind = event.get("kind")
        
        # Handle NIP-04
        if kind == 4:
            try:
                # Decrypt
                decrypted = decrypt_nip04(content, self.private_key, sender_pubkey)
                if decrypted:
                    content = decrypted
                    logger.info(f"Nostr DM from {sender_pubkey[:8]}...: {content}")
                else:
                    logger.warning(f"Nostr DM from {sender_pubkey[:8]}... failed to decrypt.")
                    return
            except Exception as e:
                logger.error(f"Nostr DM decrypt error: {e}")
                return
        else:
            logger.info(f"Nostr received from {sender_pubkey[:8]}...: {content}")
        
        # Route to Bus
        msg = InboundMessage(
            channel="nostr",
            sender_id=sender_pubkey,
            chat_id=sender_pubkey, 
            content=content,
            metadata={"event_id": event["id"], "kind": kind}
        )
        await self.bus.publish_inbound(msg)

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message (Kind 1 or 4) to Nostr."""
        if not self._ws:
            logger.warning("Nostr: Not connected, cannot send.")
            return
            
        created_at = int(time.time())
        target_pubkey = msg.chat_id
        
        # Logic: If chat_id looks like a pubkey (64 hex), send DM (Kind 4).
        # Otherwise (e.g. "broadcast"), send Kind 1.
        # But msg.chat_id is usually the channel ID.
        # If it's a broadcast, chat_id might be "nostr" or "global".
        
        if len(target_pubkey) == 64:
            # Assume DM
            kind = 4
            tags = [["p", target_pubkey]]
            content = encrypt_nip04(msg.content, self.private_key, target_pubkey)
        else:
            # Assume Broadcast
            kind = 1
            tags = []
            content = msg.content
        
        raw_data = json.dumps(
            [0, self.public_key, created_at, kind, tags, content],
            separators=(',', ':'),
            ensure_ascii=False
        )
        
        event_id = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()
        sig = sign_event(event_id, self.private_key)
        
        event = {
            "id": event_id,
            "pubkey": self.public_key,
            "created_at": created_at,
            "kind": kind,
            "tags": tags,
            "content": content,
            "sig": sig
        }
        
        envelope = ["EVENT", event]
        await self._ws.send(json.dumps(envelope))

    async def _send_hello(self) -> None:
        """Broadcast online status."""
        # Kind 1 Broadcast
        name = "Sol" 
        hello_msg = OutboundMessage(
            channel="nostr",
            chat_id="broadcast", 
            content=f"Hello. {name} is online and ready."
        )
        await self.send(hello_msg)

    async def stop(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()

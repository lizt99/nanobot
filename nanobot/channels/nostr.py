"""Nostr channel implementation using websockets and BIP-340 with NIP-04 DM Support."""

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

from nanobot.bus.events import OutboundMessage, InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import Config
from nanobot.utils.bip340 import generate_keypair, sign_event, pubkey_gen

# --- NIP-04 Crypto Helpers ---
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.asymmetric import ec

def get_shared_secret(priv_key_hex: str, pub_key_hex: str) -> bytes:
    try:
        import coincurve
        sk = coincurve.PrivateKey(bytes.fromhex(priv_key_hex))
        pk_bytes = bytes.fromhex("02" + pub_key_hex)
        pk = coincurve.PublicKey(pk_bytes)
        return sk.ecdh(pk.format())
    except ImportError:
        # Fallback to cryptography
        priv_int = int(priv_key_hex, 16)
        private_key = ec.derive_private_key(priv_int, ec.SECP256K1(), default_backend())
        p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
        x = int(pub_key_hex, 16)
        y_sq = (pow(x, 3, p) + 7) % p
        y = pow(y_sq, (p + 1) // 4, p)
        if y % 2 != 0:
            y = p - y
        public_numbers = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1())
        public_key = public_numbers.public_key(default_backend())
        return private_key.exchange(ec.ECDH(), public_key)

def encrypt_nip04(message: str, shared_secret: bytes) -> str:
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(shared_secret), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(message.encode('utf-8')) + padder.finalize()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode('utf-8') + "?iv=" + base64.b64encode(iv).decode('utf-8')

def decrypt_nip04(payload: str, shared_secret: bytes) -> str:
    try:
        parts = payload.split("?iv=")
        if len(parts) != 2:
            return payload # Not encrypted or invalid
        
        ciphertext = base64.b64decode(parts[0])
        iv = base64.b64decode(parts[1])
        
        cipher = Cipher(algorithms.AES(shared_secret), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        return data.decode('utf-8')
    except Exception as e:
        logger.error(f"Nostr Decryption Error: {e}")
        return f"[Decryption Failed: {e}]"

class NostrChannel(BaseChannel):
    """
    Nostr channel for bot-to-bot communication.
    Supports NIP-01 and NIP-04 (DMs).
    """
    
    name = "nostr"
    
    def __init__(self, config: Any, bus: MessageBus, identity_loader: Any = None):
        super().__init__(config, bus)
        self.config = config
        self.identity_loader = identity_loader
        self.private_key = config.private_key or self._load_key_from_aieos()
        self.relay_url = config.relay_url or "ws://msp-nostr-relay:8080"
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._subscription_id = f"nanobot-{uuid.uuid4().hex[:8]}"

    def _load_key_from_aieos(self) -> str | None:
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
        if not self.config.enabled:
            return
            
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
        
        while self._running:
            try:
                logger.info(f"Nostr: Connecting to {self.relay_url}...")
                async with websockets.connect(self.relay_url) as ws:
                    self._ws = ws
                    logger.info("Nostr: Connected.")
                    
                    # Subscribe to Kind 1 (Chat) and Kind 4 (DM)
                    # Look back 1 hour to catch missed messages
                    since_ts = int(time.time()) - 3600 
                    req = [
                        "REQ", 
                        self._subscription_id, 
                        {"kinds": [1, 4], "limit": 50, "since": since_ts}
                    ]
                    await ws.send(json.dumps(req))
                    
                    await self._send_hello()
                    await self._listen_loop(ws)
                    
            except Exception as e:
                logger.error(f"Nostr error: {e}")
                self._ws = None
                await asyncio.sleep(5)

    async def _listen_loop(self, ws):
        async for message in ws:
            try:
                data = json.loads(message)
                msg_type = data[0]
                if msg_type == "EVENT":
                    await self._handle_event(data[2])
            except json.JSONDecodeError:
                pass

    async def _handle_event(self, event: dict) -> None:
        if event["pubkey"] == self.public_key:
            return
            
        content = event["content"]
        sender_pubkey = event["pubkey"]
        kind = event["kind"]
        
        # Handle NIP-04 DM
        if kind == 4:
            try:
                shared_secret = get_shared_secret(self.private_key, sender_pubkey)
                content = decrypt_nip04(content, shared_secret)
                logger.info(f"Nostr DM from {sender_pubkey[:8]}: {content}")
            except Exception as e:
                logger.error(f"Failed to decrypt DM: {e}")
                content = "[Encrypted Message]"
        else:
            logger.info(f"Nostr Note from {sender_pubkey[:8]}: {content}")
        
        msg = InboundMessage(
            channel="nostr",
            sender_id=sender_pubkey,
            chat_id=sender_pubkey, 
            content=content,
            metadata={"event_id": event["id"], "kind": kind}
        )
        await self.bus.publish_inbound(msg)

    async def send(self, msg: OutboundMessage) -> None:
        if not self._ws:
            return
            
        created_at = int(time.time())
        content = msg.content
        tags = []
        kind = 1
        
        # Determine if DM (Kind 4)
        # If chat_id is a 64-char hex string, treat as pubkey for DM
        if len(msg.chat_id) == 64:
            try:
                int(msg.chat_id, 16) # Verify hex
                kind = 4
                tags = [["p", msg.chat_id]]
                shared_secret = get_shared_secret(self.private_key, msg.chat_id)
                content = encrypt_nip04(content, shared_secret)
            except ValueError:
                pass # Not a valid pubkey, fallback to Kind 1
        
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
        
        await self._ws.send(json.dumps(["EVENT", event]))

    async def _send_hello(self) -> None:
        pass # Silence hello to reduce noise

    async def stop(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()

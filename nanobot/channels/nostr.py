"""Nostr channel implementation using websockets and BIP-340."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
import hashlib
from typing import Any

import websockets
from loguru import logger

from nanobot.bus.events import OutboundMessage, InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import Config
from nanobot.utils.bip340 import generate_keypair, sign_event, pubkey_gen

class NostrChannel(BaseChannel):
    """
    Nostr channel for bot-to-bot communication.
    
    Supports:
    - NIP-01: Basic protocol (EVENT, REQ, CLOSE)
    - Kind 1: Short text note (Chat)
    """
    
    name = "nostr"
    
    def __init__(self, config: Any, bus: MessageBus, identity_loader: Any = None):
        super().__init__(config, bus)
        self.config = config
        self.identity_loader = identity_loader
        
        # Priority: Config > Env > AIEOS > Generate New
        self.private_key = config.private_key or self._load_key_from_aieos()
        
        # Hardcoded SuperAdmin
        self.SUPER_ADMIN_NPUB = "npub1mla74zqczgruewwpmmanak8qxjgjna0mw7hyqgxvqmcglf5g5qzs9ak9g8"
        self.relay_url = config.relay_url or "ws://msp-nostr-relay:8080" # Default internal docker DNS
        
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._subscription_id = f"nanobot-{uuid.uuid4().hex[:8]}"

    def _load_key_from_aieos(self) -> str | None:
        """Try to load private key from AIEOS identity."""
        try:
            from nanobot.utils.aieos import AIEOSLoader
            from pathlib import Path
            # Assuming workspace is at /root/.nanobot/workspace in container, or we find a way to access it.
            # But wait, channels don't have easy access to workspace path unless passed.
            # Workaround: Assume standard container path /app/workspace or /root/.nanobot/workspace
            # Better: Config should pass workspace. For now, rely on AIEOSLoader env var lookup.
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
            # Derive pubkey from private key
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
                    
                    # 3. Subscribe to Kind 1 (Text Note)
                    # Filter: kinds=[1], since [now]
                    req = [
                        "REQ", 
                        self._subscription_id, 
                        {"kinds": [1], "limit": 0} # limit 0 = only new messages? No, since=now is better
                    ]
                    # Add 'since' to avoid fetching history for now
                    req[2]["since"] = int(time.time())
                    
                    await ws.send(json.dumps(req))
                    
                    # 4. Broadcast Hello
                    await self._send_hello()
                    
                    # 5. Listen Loop
                    await self._listen_loop(ws)
                    
            except Exception as e:
                logger.error(f"Nostr error: {e}")
                self._ws = None
                await asyncio.sleep(5) # Retry delay

    async def _listen_loop(self, ws):
        async for message in ws:
            try:
                data = json.loads(message)
                msg_type = data[0]
                
                if msg_type == "EVENT":
                    sub_id = data[1]
                    event = data[2]
                    await self._handle_event(event)
                elif msg_type == "OK":
                    pass # Acknowledgement
                elif msg_type == "EOSE":
                    pass # End of stored events
                    
            except json.JSONDecodeError:
                pass

    async def _handle_event(self, event: dict) -> None:
        """Handle incoming Nostr event."""
        # Ignore own events
        if event["pubkey"] == self.public_key:
            return
            
        content = event["content"]
        sender_pubkey = event["pubkey"]
        
        # Determine if this is a command from SuperAdmin
        # (Naive check: is sender SuperAdmin?)
        # Note: npub needs decoding to hex to match event['pubkey']. 
        # For now, I'll just log receiving.
        
        logger.info(f"Nostr received from {sender_pubkey[:8]}...: {content}")
        
        # Route to Bus
        # We treat Nostr as a channel named 'nostr'
        # Chat ID is the sender's pubkey
        msg = InboundMessage(
            channel="nostr",
            sender_id=sender_pubkey,
            chat_id=sender_pubkey, 
            content=content,
            metadata={"event_id": event["id"]}
        )
        await self.bus.publish_inbound(msg)

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message (Kind 1) to Nostr."""
        if not self._ws:
            logger.warning("Nostr: Not connected, cannot send.")
            return
            
        # Construct Event
        created_at = int(time.time())
        kind = 1
        tags = [] # TODO: Add 'p' tag if replying to DM? For now, public broadcast.
        content = msg.content
        
        # Serialize for ID (NIP-01)
        # [0, pubkey, created_at, kind, tags, content]
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
        # Get bot name from identity if possible
        name = "Nanobot" 
        # (Could fetch from env or AIEOS loader)
        
        hello_msg = OutboundMessage(
            channel="nostr",
            chat_id="broadcast",
            content=f"Hello world. {name} is online."
        )
        await self.send(hello_msg)

    async def stop(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()

import asyncio
import json
import os
import websockets
from pathlib import Path
from loguru import logger
from nanobot.utils.crypto import decrypt_soul

async def fetch_and_incarnate(soul_id: str, password: str, relay_url: str, workspace: Path) -> Path | None:
    """
    Fetch encrypted soul from Nostr, decrypt, and save to workspace.
    Returns path to the decrypted JSON file.
    
    This implements the 'Pull' model of Paradigm A.
    """
    logger.info(f"Incarnation: Fetching Soul '{soul_id}' from {relay_url}...")
    
    # Filter for Kind 30000 with d=soul_id
    req = json.dumps([
        "REQ", "incarnation-1",
        {"kinds": [30000], "#d": [soul_id], "limit": 1}
    ])
    
    try:
        async with websockets.connect(relay_url) as ws:
            await ws.send(req)
            
            # Wait for EVENT
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    
                    if data[0] == "EVENT":
                        event = data[2]
                        content = event["content"]
                        logger.info("Incarnation: Soul found. Decrypting...")
                        
                        try:
                            soul_data = decrypt_soul(content, password)
                            
                            # Save to workspace/aieos.json (ephemeral identity for this session)
                            # We don't overwrite source files, we create a runtime identity.
                            dest = workspace / "aieos_runtime.json"
                            dest.write_text(json.dumps(soul_data, indent=2), encoding="utf-8")
                            
                            logger.info(f"Incarnation: Success. Identity saved to {dest}")
                            return dest
                        except Exception as e:
                            logger.error(f"Incarnation: Decryption failed: {e}")
                            return None
                    
                    elif data[0] == "EOSE":
                        logger.warning(f"Incarnation: Soul '{soul_id}' not found on relay.")
                        return None
                        
                except asyncio.TimeoutError:
                    logger.error("Incarnation: Timeout waiting for relay response.")
                    return None
                    
    except Exception as e:
        logger.error(f"Incarnation: Connection error: {e}")
        return None

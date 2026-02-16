import os
import asyncio
from loguru import logger

async def try_incarnation(config):
    """
    Check environment variables for Soul ID and Master Key.
    If found, fetch the Soul from Nostr and inject it into the environment.
    """
    soul_id = os.getenv("NANOBOT_SOUL_ID")
    master_key = os.getenv("NANOBOT_MASTER_KEY")
    
    if not (soul_id and master_key):
        return

    # Import here to avoid circular imports
    from nanobot.utils.soul_fetcher import fetch_and_incarnate
    
    # Default to localhost for CLI usage, or msp-nostr-relay for docker
    default_relay = "ws://127.0.0.1:8080"
    if os.path.exists("/.dockerenv"):
        default_relay = "ws://msp-nostr-relay:8080"
        
    relay_url = os.getenv("NANOBOT_RELAY_URL", default_relay)
    
    logger.info(f"Boot: Attempting incarnation for {soul_id}...")
    path = await fetch_and_incarnate(soul_id, master_key, relay_url, config.workspace_path)
    
    if path:
        logger.success(f"Boot: Incarnation successful. Soul loaded from {path}")
        os.environ["NANOBOT_AIEOS_PATH"] = str(path)
        
        # Extract name for logging/prompt
        import json
        try:
            data = json.loads(path.read_text())
            # Support AIEOS format
            identity = data.get("identity", {})
            name = identity.get("names", {}).get("first") or identity.get("name")
            if name:
                os.environ["NANOBOT_NAME"] = name
        except:
            pass

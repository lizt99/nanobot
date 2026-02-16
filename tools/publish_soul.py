import asyncio
import json
import sys
import os
import hashlib
import time
import websockets
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from nanobot.utils.crypto import encrypt_soul
from nanobot.utils.bip340 import generate_keypair, sign_event

def compute_event_id(event):
    data = [
        0,
        event['pubkey'],
        event['created_at'],
        event['kind'],
        event['tags'],
        event['content']
    ]
    json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

async def publish(soul_path, password, relay_url="ws://localhost:8080"):
    with open(soul_path) as f:
        soul_data = json.load(f)
    
    # Identify Soul
    # Use 'bob' from 'souls/bob.json'
    identifier = Path(soul_path).stem 
    
    print(f"Encrypting {identifier}...")
    encrypted_content = encrypt_soul(soul_data, password)
    
    # Use a fixed Admin Key if provided via env, else ephemeral
    # In real world, this should be YOUR admin key so you can update it later.
    sk = os.getenv("ADMIN_PRIVATE_KEY")
    if not sk:
        print("No ADMIN_PRIVATE_KEY env, using ephemeral key.")
        sk, pk = generate_keypair()
    else:
        from nanobot.utils.bip340 import pubkey_gen
        pk = pubkey_gen(bytes.fromhex(sk)).hex()

    event = {
        "pubkey": pk,
        "created_at": int(time.time()),
        "kind": 30000,
        "tags": [
            ["d", identifier],
            ["name", soul_data.get("name", identifier)]
        ],
        "content": encrypted_content
    }
    
    event["id"] = compute_event_id(event)
    event["sig"] = sign_event(event["id"], sk)
    
    print(f"Publishing to {relay_url}...")
    try:
        async with websockets.connect(relay_url) as ws:
            msg = json.dumps(["EVENT", event])
            await ws.send(msg)
            # Wait for OK
            response = await ws.recv()
            print(f"Relay says: {response}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python publish_soul.py <soul.json> <password> [relay_url]")
        sys.exit(1)
        
    asyncio.run(publish(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "ws://localhost:8080"))

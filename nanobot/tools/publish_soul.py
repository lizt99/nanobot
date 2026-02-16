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

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import hashlib
import os
import json
import base64

def encrypt_soul(data: dict, password: str) -> str:
    key = hashlib.sha256(password.encode()).digest()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    payload = json.dumps(data).encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, payload, None)
    return base64.b64encode(nonce + ciphertext).decode('utf-8')

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
    print(f"DEBUG: Opening '{soul_path}' (cwd: {os.getcwd()})")
    if not os.path.exists(soul_path):
        print(f"ERROR: {soul_path} does not exist!")
    with open(soul_path) as f:
        soul_data = json.load(f)
    
    identifier = Path(soul_path).stem 
    print(f"Encrypting {identifier}...")
    encrypted_content = encrypt_soul(soul_data, password)
    
    try:
        from nostr.key import PrivateKey
        from nostr.event import Event
        print("Using 'nostr' library for signing...")
        pk_obj = PrivateKey()
        event_obj = Event(
            public_key=pk_obj.public_key.hex(),
            created_at=int(time.time()),
            kind=30000,
            tags=[
                ["d", identifier],
                ["name", soul_data.get("name", identifier)]
            ],
            content=encrypted_content
        )
        pk_obj.sign_event(event_obj)
        
        event = {
            "id": event_obj.id,
            "pubkey": event_obj.public_key,
            "created_at": event_obj.created_at,
            "kind": event_obj.kind,
            "tags": event_obj.tags,
            "content": event_obj.content,
            "sig": event_obj.signature
        }
    except ImportError:
        print("Fallback to internal bip340...")
        from nanobot.utils.bip340 import generate_keypair, sign_event, pubkey_gen
        
        sk = os.getenv("ADMIN_PRIVATE_KEY")
        if not sk:
            sk, pk = generate_keypair()
        else:
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

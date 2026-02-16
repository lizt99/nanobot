import json
import sys
import os
from pathlib import Path

# Add project root
sys.path.append(str(Path(__file__).parent.parent / "nanobot"))

try:
    from nanobot.utils.crypto import encrypt_soul, decrypt_soul
except ImportError:
    # If package not installed in editable mode, path append might need adjustment
    sys.path.append(str(Path(__file__).parent.parent))
    from nanobot.utils.crypto import encrypt_soul, decrypt_soul

def test_crypto():
    print("Testing Crypto Roundtrip...")
    soul = {"name": "TestBot", "role": "Tester", "secret": "42"}
    password = "correct-horse-battery-staple"
    
    blob = encrypt_soul(soul, password)
    print(f"Encrypted blob: {blob[:20]}...")
    
    decrypted = decrypt_soul(blob, password)
    print(f"Decrypted: {decrypted}")
    
    assert decrypted == soul
    print("SUCCESS: Roundtrip passed.")
    
    try:
        decrypt_soul(blob, "wrong")
        print("FAILURE: Wrong password did not raise error.")
    except Exception as e:
        print(f"SUCCESS: Wrong password raised error: {e}")

if __name__ == "__main__":
    test_crypto()

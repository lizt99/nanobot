import json
import hashlib
import base64
from nanobot.utils.bip340 import pubkey_gen
from nanobot.utils.crypto import encrypt_soul as utils_encrypt_soul

class SoulCasterTool:
    def execute(self, action, **kwargs):
        if action == "mint_soul":
            return self.mint_soul(
                kwargs.get("name"),
                kwargs.get("role"),
                kwargs.get("password")
            )
        elif action == "encrypt_soul":
            return self.encrypt_soul(
                kwargs.get("soul_json"),
                kwargs.get("master_key")
            )
        else:
            raise ValueError(f"Unknown action: {action}")

    def mint_soul(self, name, role, password):
        if not name or not role or not password:
            raise ValueError("name, role, and password are required for mint_soul")

        # Derive private key from password (SHA256)
        private_key_bytes = hashlib.sha256(password.encode()).digest()
        private_key_hex = private_key_bytes.hex()

        # Generate public key (BIP340)
        public_key_bytes = pubkey_gen(private_key_bytes)
        public_key_hex = public_key_bytes.hex()

        soul_data = {
            "name": name,
            "role": role,
            "private_key": private_key_hex,
            "public_key": public_key_hex,
            "relays": ["ws://msp-nostr-relay:8080"],
            "skills": ["worker"] # Default skill for now? Or empty?
        }
        
        return json.dumps(soul_data)

    def encrypt_soul(self, soul_json, master_key):
        if not soul_json or not master_key:
             raise ValueError("soul_json and master_key are required for encrypt_soul")
        
        if isinstance(soul_json, str):
            try:
                soul_data = json.loads(soul_json)
            except json.JSONDecodeError:
                # If it's not JSON, maybe it's already a dict passed as string repr?
                # But safer to assume valid JSON string as input.
                raise ValueError("soul_json must be a valid JSON string")
        elif isinstance(soul_json, dict):
            soul_data = soul_json
        else:
            raise ValueError("soul_json must be a string or dict")

        # Encrypt using nanobot.utils.crypto.AESGCM (via helper)
        encrypted_b64 = utils_encrypt_soul(soul_data, master_key)
        return encrypted_b64

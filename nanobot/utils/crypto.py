"""
Crypto utilities for Soul encryption (AES-256-GCM).
Used for Paradigm A (Password Paradigm) of Digital Immortality.
"""

import os
import json
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt_soul(data: dict, password: str) -> str:
    """
    Encrypt a dictionary (Soul) using a password.
    
    Algorithm: AES-256-GCM
    Key Derivation: SHA256(password) - Simple but effective for high-entropy passwords.
    Output: Base64(Nonce + Ciphertext)
    """
    key = hashlib.sha256(password.encode()).digest()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    
    payload = json.dumps(data).encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, payload, None)
    
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode('utf-8')

def decrypt_soul(blob: str, password: str) -> dict:
    """
    Decrypt a Soul blob using a password.
    
    Input: Base64(Nonce + Ciphertext)
    Returns: Dictionary
    Raises: cryptography.exceptions.InvalidTag if password is wrong.
    """
    key = hashlib.sha256(password.encode()).digest()
    
    try:
        raw = base64.b64decode(blob)
        nonce = raw[:12]
        ciphertext = raw[12:]
        
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")

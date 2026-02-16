"""
Minimal BIP-340 Schnorr Signatures for Nostr.
Adapted from the reference implementation: https://github.com/bitcoin/bips/blob/master/bip-0340/reference.py
"""

import hashlib
import binascii
import os

p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G_x = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
G_y = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

def point_add(P1, P2):
    if P1 is None:
        return P2
    if P2 is None:
        return P1
    (x1, y1) = P1
    (x2, y2) = P2
    if x1 == x2 and y1 != y2:
        return None
    if x1 == x2:
        lam = (3 * x1 * x1 * pow(2 * y1, p - 2, p)) % p
    else:
        lam = ((y2 - y1) * pow(x2 - x1, p - 2, p)) % p
    x3 = (lam * lam - x1 - x2) % p
    y3 = (lam * (x1 - x3) - y1) % p
    return (x3, y3)

def point_mul(P, n):
    R = None
    for i in range(256):
        if (n >> i) & 1:
            R = point_add(R, P)
        P = point_add(P, P)
    return R

def bytes_from_int(x):
    return x.to_bytes(32, byteorder="big")

def bytes_from_point(P):
    return bytes_from_int(P[0])

def xor_bytes(b0, b1):
    return bytes(x ^ y for (x, y) in zip(b0, b1))

def lift_x(x):
    if x >= p:
        return None
    y_sq = (pow(x, 3, p) + 7) % p
    y = pow(y_sq, (p + 1) // 4, p)
    if pow(y, 2, p) != y_sq:
        return None
    return (x, y if y % 2 == 0 else p - y)

def pubkey_gen(seckey):
    x = int.from_bytes(seckey, byteorder="big")
    if not (1 <= x <= n - 1):
        raise ValueError('The secret key must be an integer in the range 1..n-1.')
    P = point_mul((G_x, G_y), x)
    return bytes_from_point(P)

def sha256(b):
    return hashlib.sha256(b).digest()

def tagged_hash(tag, msg):
    tag_hash = sha256(tag.encode())
    return sha256(tag_hash + tag_hash + msg)

def schnorr_sign(msg, seckey, aux_rand):
    if len(msg) != 32:
        raise ValueError('The message must be a 32-byte array.')
    d0 = int.from_bytes(seckey, byteorder="big")
    if not (1 <= d0 <= n - 1):
        raise ValueError('The secret key must be an integer in the range 1..n-1.')
    P = point_mul((G_x, G_y), d0)
    if P[1] % 2 != 0:
        d = n - d0
    else:
        d = d0
    t = xor_bytes(bytes_from_int(d), tagged_hash("BIP0340/aux", aux_rand))
    k0 = int.from_bytes(tagged_hash("BIP0340/nonce", t + bytes_from_point(P) + msg), byteorder="big") % n
    if k0 == 0:
        raise RuntimeError('Failure. This happens only with negligible probability.')
    R = point_mul((G_x, G_y), k0)
    if R[1] % 2 != 0:
        k = n - k0
    else:
        k = k0
    e = int.from_bytes(tagged_hash("BIP0340/challenge", bytes_from_point(R) + bytes_from_point(P) + msg), byteorder="big") % n
    sig = bytes_from_point(R) + bytes_from_int((k + e * d) % n)
    return sig

def schnorr_verify(msg, pubkey, sig):
    if len(msg) != 32:
        raise ValueError('The message must be a 32-byte array.')
    if len(pubkey) != 32:
        raise ValueError('The public key must be a 32-byte array.')
    if len(sig) != 64:
        raise ValueError('The signature must be a 64-byte array.')
    P = lift_x(int.from_bytes(pubkey, byteorder="big"))
    if P is None:
        return False
    r = int.from_bytes(sig[0:32], byteorder="big")
    s = int.from_bytes(sig[32:64], byteorder="big")
    if r >= p or s >= n:
        return False
    e = int.from_bytes(tagged_hash("BIP0340/challenge", sig[0:32] + pubkey + msg), byteorder="big") % n
    R = point_add(point_mul((G_x, G_y), s), point_mul(P, n - e))
    if R is None or R[1] % 2 != 0 or R[0] != r:
        return False
    return True

# Helper for Nanobot
def generate_keypair():
    while True:
        seckey = os.urandom(32)
        try:
            pubkey = pubkey_gen(seckey)
            return seckey.hex(), pubkey.hex()
        except ValueError:
            continue # Try again if key is out of range

def sign_event(event_id_hex: str, privkey_hex: str) -> str:
    msg = bytes.fromhex(event_id_hex)
    seckey = bytes.fromhex(privkey_hex)
    aux = os.urandom(32)
    sig = schnorr_sign(msg, seckey, aux)
    return sig.hex()

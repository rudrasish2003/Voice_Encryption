"""AES-GCM encryption for voiceprint vectors at rest.

The key is read from VOICEPRINT_ENC_KEY (base64, 32 bytes) and must live outside
the data store -- in .env locally, in a secrets manager in production.
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_vector(vector_bytes: bytes, key_b64: str) -> str:
    key = base64.b64decode(key_b64)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, vector_bytes, None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_vector(blob_b64: str, key_b64: str) -> bytes:
    key = base64.b64decode(key_b64)
    aesgcm = AESGCM(key)
    raw = base64.b64decode(blob_b64)
    nonce, ciphertext = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None)

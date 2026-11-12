"""Generate a JWT secret and a voiceprint encryption key for .env.

Usage: python scripts/generate_keys.py
"""
import base64
import os
import secrets


def main() -> None:
    jwt_secret = secrets.token_urlsafe(48)
    enc_key = base64.b64encode(os.urandom(32)).decode("utf-8")
    print(f"JWT_SECRET={jwt_secret}")
    print(f"VOICEPRINT_ENC_KEY={enc_key}")


if __name__ == "__main__":
    main()

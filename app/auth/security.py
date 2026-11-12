"""JWT auth with scope-based authorization.

DEV-ONLY: authenticate_dev_user checks a single admin credential from .env.
Replace with real user management (per-user accounts, hashed passwords,
role assignment) before Phase 5 / production use.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token", auto_error=False)

ALL_SCOPES = [
    "people:write",
    "people:read",
    "people:delete",
    "identify:write",
    "identify:read",
    "audit:read",
]


def create_access_token(subject: str, scopes: list[str], expires_minutes: Optional[int] = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.jwt_expire_minutes)
    payload = {"sub": subject, "scopes": scopes, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")


def require_scopes(*required: str):
    def dependency(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
        if token is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
        payload = decode_token(token)
        token_scopes = set(payload.get("scopes", []))
        if not set(required).issubset(token_scopes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient scope")
        return payload

    return dependency


def authenticate_dev_user(username: str, password: str) -> Optional[list[str]]:
    settings = get_settings()
    if username == settings.admin_username and password == settings.admin_password:
        return ALL_SCOPES
    return None

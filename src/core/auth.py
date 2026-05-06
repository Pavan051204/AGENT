"""Authentication utilities – JWT tokens and password hashing."""

import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request
from src.settings import get_config


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_token(user_id: str, username: str, role: str, expires_hours: int = 24) -> str:
    """Create a JWT token containing user info."""
    config = get_config()
    payload = {
        "user_id": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=expires_hours),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token.  Returns the payload dict or None."""
    config = get_config()
    try:
        return jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ---------------------------------------------------------------------------
# FastAPI dependency – extracts user from Authorization header
# ---------------------------------------------------------------------------

def get_current_user(request: Request) -> dict:
    """FastAPI dependency that extracts the current user from the JWT token.

    Checks the ``Authorization: Bearer <token>`` header first, then falls back
    to a ``token`` query-parameter (handy for quick testing).
    """
    auth_header = request.headers.get("Authorization", "")
    token: Optional[str] = None

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload

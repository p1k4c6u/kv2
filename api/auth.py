# auth.py
"""
Simple password-based authentication with JWT tokens.
"""

import jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

security = HTTPBearer()


def create_token(password: str) -> str | None:
    """
    Verify password and create a JWT token if valid.
    Returns None if password is incorrect.
    """
    settings = get_settings()

    if password != settings.APP_PASSWORD:
        return None

    expiration = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_EXPIRATION_DAYS
    )
    payload = {
        "exp": expiration,
        "iat": datetime.now(timezone.utc),
        "sub": "authenticated_user",
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> bool:
    """
    Verify the JWT token from the Authorization header.
    Raises HTTPException if invalid.
    """
    settings = get_settings()
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return True
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

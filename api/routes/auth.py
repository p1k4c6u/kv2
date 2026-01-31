# routes/auth.py
"""
Authentication routes.
"""

from fastapi import APIRouter, HTTPException, status

from ..schemas import LoginRequest, LoginResponse
from ..auth import create_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate with password and receive a JWT token.
    """
    token = create_token(request.password)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password"
        )

    return LoginResponse(token=token)

"""Authentication routes."""
import logging
import os
from fastapi import APIRouter, Depends, Response, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..db import get_db
from ..models import User
from ..security import sign_jwt, verify_jwt, hash_password, verify_password

logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

COOKIE_NAME = "session"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")

router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginIn(BaseModel):
    username: str
    password: str

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency to get current authenticated user."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Not authenticated")
    ok, payload = verify_jwt(token)
    if not ok:
        raise HTTPException(401, "Invalid session")
    username = payload.get("sub")
    u = db.query(User).filter(User.username == username).first()
    if not u:
        raise HTTPException(401, "User not found")
    return u

@router.post("/login")
@limiter.limit("5/minute")  # Rate limit: 5 attempts per minute
async def login(request: Request, payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    """Login endpoint with rate limiting."""
    logger.info(f"Login attempt for user: {payload.username}")
    u = db.query(User).filter(User.username == payload.username).first()

    if not u or not verify_password(payload.password, u.password_hash):
        logger.warning(f"Failed login attempt for user: {payload.username}")
        raise HTTPException(401, "Fel användarnamn eller lösenord")

    token = sign_jwt({"sub": u.username})
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/"
    )
    logger.info(f"Successful login for user: {payload.username}")
    return {"ok": True, "user": {"username": u.username}}

@router.post("/logout")
def logout(response: Response):
    """Logout endpoint."""
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}

@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """Get current user info."""
    return {"username": user.username}

@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change password endpoint."""
    if not verify_password(payload.current_password, user.password_hash):
        logger.warning(f"Failed password change attempt for user: {user.username}")
        raise HTTPException(400, "Fel nuvarande lösenord")

    if not payload.new_password or len(payload.new_password) < 8:
        raise HTTPException(400, "Nytt lösenord måste vara minst 8 tecken")

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    logger.info(f"Password changed for user: {user.username}")
    return {"ok": True}

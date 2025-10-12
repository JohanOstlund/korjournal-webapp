"""
Dependencies for FastAPI dependency injection.
"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import verify_jwt
import os

COOKIE_NAME = "session"

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

def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """Dependency to verify admin privileges."""
    if not user.is_admin:
        raise HTTPException(403, "Admin privileges required")
    return user

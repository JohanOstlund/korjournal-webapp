"""
Admin user management routes.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..schemas import UserOut, CreateUserIn
from ..dependencies import get_admin_user
from ..security import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/users", tags=["admin"])

@router.post("", response_model=UserOut)
def create_user(
    payload: CreateUserIn,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin endpoint to create a new user."""
    if not payload.username or not payload.password:
        raise HTTPException(400, "Användarnamn och lösenord krävs")

    if len(payload.password) < 8:
        raise HTTPException(400, "Lösenord måste vara minst 8 tecken")

    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(400, "Användaren finns redan")

    new_user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_admin=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"Admin {admin.username} created new user: {new_user.username}")
    return UserOut(id=new_user.id, username=new_user.username)

@router.get("", response_model=List[UserOut])
def list_users(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin endpoint to list all users."""
    users = db.query(User).order_by(User.username).all()
    return [UserOut(id=u.id, username=u.username) for u in users]

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin endpoint to delete a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Användare hittades inte")

    if user.is_admin:
        raise HTTPException(400, "Kan inte ta bort admin-användare")

    if user.id == admin.id:
        raise HTTPException(400, "Kan inte ta bort sig själv")

    db.delete(user)
    db.commit()
    logger.info(f"Admin {admin.username} deleted user: {user.username}")
    return {"status": "deleted"}

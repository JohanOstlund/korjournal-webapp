"""
User settings management routes.
"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, HASetting
from ..schemas import SettingsOut, SettingsIn
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("", response_model=SettingsOut)
def get_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user-specific HA settings."""
    h = db.query(HASetting).filter(HASetting.user_id == user.id).first()
    return SettingsOut(
        ha_base_url=h.base_url if h else None,
        ha_odometer_entity=h.odometer_entity if h else None,
        ha_token_set=bool(h and h.token),
        force_domain=h.force_domain if h else None,
        force_service=h.force_service if h else None,
        force_data_json=json.loads(h.force_data_json) if h and h.force_data_json else None,
    )

@router.put("", response_model=SettingsOut)
def put_settings(payload: SettingsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update user-specific HA settings."""
    h = db.query(HASetting).filter(HASetting.user_id == user.id).first()
    if not h:
        h = HASetting(user_id=user.id)
        db.add(h)
    if payload.ha_base_url is not None: h.base_url = payload.ha_base_url or None
    if payload.ha_odometer_entity is not None: h.odometer_entity = payload.ha_odometer_entity or None
    if payload.force_domain is not None: h.force_domain = payload.force_domain or None
    if payload.force_service is not None: h.force_service = payload.force_service or None
    if payload.force_data_json is not None: h.force_data_json = json.dumps(payload.force_data_json) if payload.force_data_json else None
    if payload.ha_token is not None and payload.ha_token.strip():
        h.token = payload.ha_token.strip()
    h.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(h)
    logger.info(f"Settings updated for user: {user.username}")
    return get_settings(user, db)

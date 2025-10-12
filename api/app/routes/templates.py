"""
Trip templates routes.
"""
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import TripTemplate, User
from ..schemas import TemplateIn, TemplateOut
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/templates", tags=["templates"])

@router.get("", response_model=List[TemplateOut])
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all templates for current user."""
    tpls = db.query(TripTemplate).filter(TripTemplate.user_id == user.id).order_by(TripTemplate.name.asc()).all()
    out = []
    for t in tpls:
        out.append(TemplateOut(
            id=t.id,
            name=t.name,
            default_purpose=t.default_purpose,
            business=t.business,
            default_distance_km=t.default_distance_km,
            default_vehicle_reg=t.default_vehicle_reg,
            default_driver_name=t.default_driver_name,
            default_start_address=t.default_start_address,
            default_end_address=t.default_end_address,
        ))
    return out

@router.post("", response_model=TemplateOut)
def create_template(payload: TemplateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new template."""
    exists = db.query(TripTemplate).filter(TripTemplate.user_id == user.id, TripTemplate.name == payload.name).first()
    if exists:
        raise HTTPException(400, "En mall med detta namn finns redan")
    t = TripTemplate(
        user_id=user.id,
        name=payload.name,
        default_purpose=payload.default_purpose,
        business=payload.business,
        default_distance_km=payload.default_distance_km,
        default_vehicle_reg=payload.default_vehicle_reg,
        default_driver_name=payload.default_driver_name,
        default_start_address=payload.default_start_address,
        default_end_address=payload.default_end_address,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    logger.info(f"Template created: {t.name}, User={user.username}")
    return TemplateOut(
        id=t.id, name=t.name, default_purpose=t.default_purpose,
        business=t.business, default_distance_km=t.default_distance_km,
        default_vehicle_reg=t.default_vehicle_reg,
        default_driver_name=t.default_driver_name,
        default_start_address=t.default_start_address,
        default_end_address=t.default_end_address
    )

@router.put("/{tpl_id}", response_model=TemplateOut)
def update_template(tpl_id: int, payload: TemplateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update an existing template."""
    t = db.query(TripTemplate).filter(TripTemplate.id == tpl_id, TripTemplate.user_id == user.id).first()
    if not t:
        raise HTTPException(404, "Template not found")

    if payload.name and payload.name != t.name:
        exists = db.query(TripTemplate).filter(TripTemplate.user_id == user.id, TripTemplate.name == payload.name).first()
        if exists:
            raise HTTPException(400, "En mall med detta namn finns redan")

    t.name = payload.name
    t.default_purpose = payload.default_purpose
    t.business = payload.business
    t.default_distance_km = payload.default_distance_km
    t.default_vehicle_reg = payload.default_vehicle_reg
    t.default_driver_name = payload.default_driver_name
    t.default_start_address = payload.default_start_address
    t.default_end_address = payload.default_end_address
    t.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(t)
    logger.info(f"Template updated: {t.name}, User={user.username}")
    return TemplateOut(
        id=t.id,
        name=t.name,
        default_purpose=t.default_purpose,
        business=t.business,
        default_distance_km=t.default_distance_km,
        default_vehicle_reg=t.default_vehicle_reg,
        default_driver_name=t.default_driver_name,
        default_start_address=t.default_start_address,
        default_end_address=t.default_end_address,
    )

@router.delete("/{tpl_id}")
def delete_template(tpl_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a template."""
    t = db.query(TripTemplate).filter(TripTemplate.id == tpl_id, TripTemplate.user_id == user.id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    db.delete(t)
    db.commit()
    logger.info(f"Template deleted: ID={tpl_id}, User={user.username}")
    return {"status": "deleted"}

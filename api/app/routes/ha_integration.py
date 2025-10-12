"""
Home Assistant integration routes.
"""
import asyncio
import json
import logging
import os
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, HASetting
from ..schemas import HAPollIn
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations/home-assistant", tags=["ha_integration"])

# ===== Configuration =====
ENV_HA_FORCE_DOMAIN = os.getenv("HA_FORCE_DOMAIN", "kia_uvo")
ENV_HA_FORCE_SERVICE = os.getenv("HA_FORCE_SERVICE", "force_update")
ENV_HA_FORCE_DATA = os.getenv("HA_FORCE_DATA")
HA_VERIFY_SSL = os.getenv("HA_VERIFY_SSL", "true").lower() == "true"

def get_ha_config(db: Session, user: User):
    """Get per-user HA settings with ENV fallback."""
    h = db.query(HASetting).filter(HASetting.user_id == user.id).first()

    base = h.base_url if h and h.base_url else os.getenv("HA_BASE_URL")
    token = h.token if h and h.token else os.getenv("HA_TOKEN")
    entity = h.odometer_entity if h and h.odometer_entity else os.getenv("HA_ODOMETER_ENTITY")

    domain = h.force_domain if h and h.force_domain else ENV_HA_FORCE_DOMAIN
    service = h.force_service if h and h.force_service else ENV_HA_FORCE_SERVICE

    data_json = None
    raw = h.force_data_json if h and h.force_data_json else ENV_HA_FORCE_DATA
    if raw:
        try:
            data_json = json.loads(raw)
        except Exception:
            data_json = None
    return base, token, entity, domain, service, data_json

@router.post("/poll")
async def ha_poll(payload: HAPollIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Poll Home Assistant for odometer value."""
    base, token, entity, *_ = get_ha_config(db, user)
    if not (base and token and (entity or payload.entity_id)):
        raise HTTPException(400, "HA Base/Token/Entity not configured")
    eid = payload.entity_id or entity
    url = f"{base}/api/states/{eid}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=10, verify=HA_VERIFY_SSL) as client:
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            logger.error(f"HA poll failed: {r.status_code} - {r.text}")
            raise HTTPException(r.status_code, f"HA states fetch failed: {r.text}")
        data = r.json()
        try:
            value_km = float(data.get("state"))
        except Exception:
            raise HTTPException(500, f"Could not parse odometer state: {data.get('state')}")
        at = datetime.utcnow()
    logger.info(f"HA poll successful for user {user.username}: {value_km} km")
    return {"status": "ok", "value_km": value_km, "entity": eid, "at": at.isoformat()}

@router.post("/force-update-and-poll")
async def ha_force_update_and_poll(
    payload: HAPollIn,
    wait_seconds: int = 15,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Force Home Assistant update then poll for odometer value."""
    base, token, entity, domain, service, data_json = get_ha_config(db, user)
    if not (base and token):
        raise HTTPException(400, "HA Base/Token not configured")
    svc_url = f"{base}/api/services/{domain}/{service}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=20, verify=HA_VERIFY_SSL) as client:
        s = await client.post(svc_url, headers=headers, json=data_json or {})
        if s.status_code not in (200, 201):
            logger.error(f"HA force update failed: {s.status_code} - {s.text}")
            raise HTTPException(s.status_code, f"HA service call failed: {s.text}")

    logger.info(f"HA force update triggered for user {user.username}, waiting {wait_seconds}s...")
    await asyncio.sleep(wait_seconds)
    return await ha_poll(payload, user, db)

import os, hashlib, json, math, asyncio
from datetime import datetime
from typing import Optional, List, Tuple

import httpx
from fastapi import FastAPI, Depends, Query, Response, HTTPException, Path, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text

from pydantic import BaseModel

from .db import SessionLocal, engine, get_db
from .models import (
    Base, Trip, Vehicle, Place, OdometerSnapshot, TripTemplate, Setting,
    User, HASetting
)
from .pdf import render_journal_pdf
from .security import sign_jwt, verify_jwt

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Körjournal API")

origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ENV_HA_FORCE_DOMAIN  = os.getenv("HA_FORCE_DOMAIN", "kia_uvo")
ENV_HA_FORCE_SERVICE = os.getenv("HA_FORCE_SERVICE", "force_update")
ENV_HA_FORCE_DATA    = os.getenv("HA_FORCE_DATA")

COOKIE_NAME = "session"
COOKIE_SECURE = os.getenv("COOKIE_SECURE","false").lower()=="true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE","lax")  # 'lax'/'none'/'strict'

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def ensure_admin(db: Session):
    username = os.getenv("ADMIN_USERNAME","admin")
    u = db.query(User).filter(User.username==username).first()
    if not u:
        u = User(username=username, password_hash=hash_pw(os.getenv("ADMIN_PASSWORD","admin")))
        db.add(u); db.commit()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token: raise HTTPException(401, "Not authenticated")
    ok, payload = verify_jwt(token)
    if not ok: raise HTTPException(401, "Invalid session")
    username = payload.get("sub")
    u = db.query(User).filter(User.username==username).first()
    if not u: raise HTTPException(401, "User not found")
    return u

# ----- Helpers -----
def get_ha_config(db: Session, user: User):
    """Per-user HA-inställningar med ENV som fallback."""
    h = db.query(HASetting).filter(HASetting.user_id == user.id).first()

    base = h.base_url if h and h.base_url else os.getenv("HA_BASE_URL")
    token = h.token    if h and h.token    else os.getenv("HA_TOKEN")
    entity= h.odometer_entity if h and h.odometer_entity else os.getenv("HA_ODOMETER_ENTITY")

    domain  = h.force_domain if h and h.force_domain else ENV_HA_FORCE_DOMAIN
    service = h.force_service if h and h.force_service else ENV_HA_FORCE_SERVICE

    data_json = None
    raw = h.force_data_json if h and h.force_data_json else ENV_HA_FORCE_DATA
    if raw:
        try: data_json = json.loads(raw)
        except Exception: data_json = None
    return base, token, entity, domain, service, data_json

def ensure_no_overlap(db: Session, user_id: int, vehicle_id: int, start: datetime, end: Optional[datetime], exclude_id: Optional[int]=None):
    q = db.query(Trip).filter(Trip.user_id==user_id, Trip.vehicle_id==vehicle_id)
    if exclude_id:
        q = q.filter(Trip.id != exclude_id)
    if end is None:
        q = q.filter(Trip.ended_at.is_(None) | and_(Trip.started_at <= start, Trip.ended_at > start))
    else:
        q = q.filter(
            or_(
                and_(Trip.started_at <= start, Trip.ended_at > start),
                and_(Trip.started_at < end,   Trip.ended_at >= end),
                and_(Trip.started_at >= start, Trip.ended_at <= end),
                and_(Trip.ended_at.is_(None), Trip.started_at <= end),
            )
        )
    if db.query(q.exists()).scalar():
        raise HTTPException(status_code=400, detail="Overlapping/active trip for the same vehicle")

def odo_delta_distance(start_odo: Optional[float], end_odo: Optional[float]) -> Optional[float]:
    if start_odo is None or end_odo is None:
        return None
    d = end_odo - start_odo
    if d < 0:
        return None
    return round(d, 1)

# ------- Startup hooks -------
@app.on_event("startup")
def _startup():
    db = SessionLocal()
    try:
        ensure_admin(db)
    finally:
        db.close()

# ---------- Pydantic ----------
class LoginIn(BaseModel):
    username: str
    password: str

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

class TripIn(BaseModel):
    vehicle_reg: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    start_odometer_km: Optional[float] = None
    end_odometer_km: Optional[float] = None
    distance_km: Optional[float] = None
    purpose: Optional[str] = None
    business: bool = True
    driver_name: Optional[str] = None
    start_address: Optional[str] = None
    end_address: Optional[str] = None

class TripOut(BaseModel):
    id: int
    vehicle_reg: str
    started_at: datetime
    ended_at: Optional[datetime]
    distance_km: Optional[float]
    start_odometer_km: Optional[float]
    end_odometer_km: Optional[float]
    purpose: Optional[str]
    business: bool
    driver_name: Optional[str] = None
    start_address: Optional[str] = None
    end_address: Optional[str] = None
    class Config:
        from_attributes = True

class StartTripIn(BaseModel):
    vehicle_reg: str
    started_at: Optional[datetime] = None
    start_odometer_km: Optional[float] = None
    purpose: Optional[str] = None
    business: bool = True
    driver_name: Optional[str] = None
    start_address: Optional[str] = None
    end_address: Optional[str] = None

class FinishTripIn(BaseModel):
    vehicle_reg: Optional[str] = None
    trip_id: Optional[int] = None
    ended_at: Optional[datetime] = None
    end_odometer_km: Optional[float] = None
    distance_km: Optional[float] = None
    purpose: Optional[str] = None
    business: Optional[bool] = None
    driver_name: Optional[str] = None
    end_address: Optional[str] = None

class TemplateIn(BaseModel):
    name: str
    default_purpose: Optional[str] = None
    business: bool = True
    default_distance_km: Optional[float] = None
    default_vehicle_reg: Optional[str] = None
    default_driver_name: Optional[str] = None
    default_start_address: Optional[str] = None
    default_end_address: Optional[str] = None

class TemplateOut(BaseModel):
    id: int
    name: str
    default_purpose: Optional[str]
    business: bool
    default_distance_km: Optional[float]
    default_vehicle_reg: Optional[str]
    default_driver_name: Optional[str]
    default_start_address: Optional[str]
    default_end_address: Optional[str]
    class Config:
        from_attributes = True

class HAPollIn(BaseModel):
    vehicle_reg: str
    entity_id: Optional[str] = None
    at: Optional[datetime] = None

class SettingsOut(BaseModel):
    ha_base_url: Optional[str] = None
    ha_odometer_entity: Optional[str] = None
    ha_token_set: bool = False
    force_domain: Optional[str] = None
    force_service: Optional[str] = None
    force_data_json: Optional[dict] = None

class SettingsIn(BaseModel):
    ha_base_url: Optional[str] = None
    ha_odometer_entity: Optional[str] = None
    ha_token: Optional[str] = None
    force_domain: Optional[str] = None
    force_service: Optional[str] = None
    force_data_json: Optional[dict] = None

# ---------- Open routes ----------
@app.post("/auth/login")
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username==payload.username).first()
    if not u or u.password_hash != hash_pw(payload.password):
        raise HTTPException(401, "Fel användarnamn eller lösenord")
    token = sign_jwt({"sub": u.username})
    response.set_cookie(
        key=COOKIE_NAME, value=token, httponly=True, secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE, path="/"
    )
    return {"ok": True, "user": {"username": u.username}}

@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}

@app.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"username": user.username}

@app.post("/auth/change-password")
def change_password(payload: ChangePasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.password_hash != hash_pw(payload.current_password):
        raise HTTPException(400, "Fel nuvarande lösenord")
    if not payload.new_password or len(payload.new_password) < 8:
        raise HTTPException(400, "Nytt lösenord måste vara minst 8 tecken")
    user.password_hash = hash_pw(payload.new_password)
    db.commit()
    return {"ok": True}

@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        print("HEALTHCHECK DB ERROR:", repr(e))
        return JSONResponse({"status": "db_error", "error": str(e)}, status_code=500)

# ---------- Protected router ----------
protected = APIRouter(dependencies=[Depends(get_current_user)])

# ----- Settings (per user) -----
@protected.get("/settings", response_model=SettingsOut)
def get_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    h = db.query(HASetting).filter(HASetting.user_id == user.id).first()
    return SettingsOut(
        ha_base_url=h.base_url if h else None,
        ha_odometer_entity=h.odometer_entity if h else None,
        ha_token_set=bool(h and h.token),
        force_domain=h.force_domain if h else None,
        force_service=h.force_service if h else None,
        force_data_json=json.loads(h.force_data_json) if h and h.force_data_json else None,
    )

@protected.put("/settings", response_model=SettingsOut)
def put_settings(payload: SettingsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    h = db.query(HASetting).filter(HASetting.user_id == user.id).first()
    if not h:
        h = HASetting(user_id=user.id)
        db.add(h)
    if payload.ha_base_url is not None:        h.base_url = payload.ha_base_url or None
    if payload.ha_odometer_entity is not None: h.odometer_entity = payload.ha_odometer_entity or None
    if payload.force_domain is not None:       h.force_domain = payload.force_domain or None
    if payload.force_service is not None:      h.force_service = payload.force_service or None
    if payload.force_data_json is not None:    h.force_data_json = json.dumps(payload.force_data_json) if payload.force_data_json else None
    if payload.ha_token is not None and payload.ha_token.strip():
        h.token = payload.ha_token.strip()
    h.updated_at = datetime.utcnow()
    db.commit(); db.refresh(h)
    return get_settings(user, db)

# ----- HA integration (per user) -----
@protected.post("/integrations/home-assistant/poll")
async def ha_poll(payload: HAPollIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    base, token, entity, *_ = get_ha_config(db, user)
    if not (base and token and (entity or payload.entity_id)):
        raise HTTPException(400, "HA Base/Token/Entity not configured")
    eid = payload.entity_id or entity
    url = f"{base}/api/states/{eid}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10, verify=False) as client:
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            raise HTTPException(r.status_code, f"HA states fetch failed: {r.text}")
        data = r.json()
        try:
            value_km = float(data.get("state"))
        except Exception:
            raise HTTPException(500, f"Could not parse odometer state: {data.get('state')}")
        at = datetime.utcnow()
    return {"status": "ok", "value_km": value_km, "entity": eid, "at": at.isoformat()}

@protected.post("/integrations/home-assistant/force-update-and-poll")
async def ha_force_update_and_poll(payload: HAPollIn, wait_seconds: int = 15, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    base, token, entity, domain, service, data_json = get_ha_config(db, user)
    if not (base and token):
        raise HTTPException(400, "HA Base/Token not configured")
    svc_url = f"{base}/api/services/{domain}/{service}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20, verify=False) as client:
        s = await client.post(svc_url, headers=headers, json=data_json or {})
        if s.status_code not in (200, 201):
            raise HTTPException(s.status_code, f"HA service call failed: {s.text}")
    await asyncio.sleep(wait_seconds)
    return await ha_poll(payload, user, db)

# ----- Trips -----
@protected.post("/trips/start", response_model=TripOut)
def start_trip(payload: StartTripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
    if not veh:
        veh = Vehicle(reg_no=payload.vehicle_reg)
        db.add(veh); db.flush()

    existing = db.query(Trip).filter(Trip.user_id==user.id, Trip.vehicle_id==veh.id, Trip.ended_at.is_(None)).first()
    if existing:
        raise HTTPException(400, "Det finns redan en pågående resa för detta fordon")

    started_at = payload.started_at or datetime.utcnow()
    ensure_no_overlap(db, user.id, veh.id, started_at, None)

    trip = Trip(
        user_id=user.id,
        vehicle_id=veh.id,
        started_at=started_at,
        ended_at=None,
        start_odometer_km=payload.start_odometer_km,
        purpose=payload.purpose,
        business=payload.business,
        driver_name=payload.driver_name,
        start_address=payload.start_address,
        end_address=payload.end_address,
    )
    db.add(trip); db.commit(); db.refresh(trip)

    return TripOut(
        id=trip.id, vehicle_reg=veh.reg_no, started_at=trip.started_at, ended_at=None,
        distance_km=None, start_odometer_km=trip.start_odometer_km, end_odometer_km=None,
        purpose=trip.purpose, business=trip.business,
        driver_name=trip.driver_name, start_address=trip.start_address, end_address=trip.end_address
    )

@protected.post("/trips/finish", response_model=TripOut)
def finish_trip(payload: FinishTripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t: Optional[Trip] = None
    if payload.trip_id:
        t = db.query(Trip).filter(Trip.id==payload.trip_id, Trip.user_id==user.id).first()
        if not t: raise HTTPException(404, "Trip not found")
        if t.ended_at is not None: raise HTTPException(400, "Trip already finished")
    else:
        if not payload.vehicle_reg:
            raise HTTPException(400, "vehicle_reg eller trip_id krävs")
        veh = db.query(Vehicle).filter(Vehicle.reg_no==payload.vehicle_reg).first()
        if not veh: raise HTTPException(404, "Vehicle not found")
        t = db.query(Trip).filter(Trip.user_id==user.id, Trip.vehicle_id==veh.id, Trip.ended_at.is_(None)).order_by(Trip.started_at.desc()).first()
        if not t: raise HTTPException(404, "Ingen pågående resa att avsluta")

    ended_at = payload.ended_at or datetime.utcnow()
    ensure_no_overlap(db, user.id, t.vehicle_id, t.started_at, ended_at, exclude_id=t.id)

    t.ended_at = ended_at
    if payload.end_odometer_km is not None:
        t.end_odometer_km = payload.end_odometer_km
    if payload.purpose is not None:
        t.purpose = payload.purpose
    if payload.business is not None:
        t.business = payload.business
    if payload.driver_name is not None and not t.driver_name:
        t.driver_name = payload.driver_name
    if payload.end_address is not None:
        t.end_address = payload.end_address

    km = payload.distance_km
    if km is None:
        km = odo_delta_distance(t.start_odometer_km, t.end_odometer_km)
    t.distance_km = km if km is not None else t.distance_km
    t.updated_at = datetime.utcnow()

    db.commit(); db.refresh(t)
    veh = db.query(Vehicle).get(t.vehicle_id)

    return TripOut(
        id=t.id, vehicle_reg=veh.reg_no, started_at=t.started_at, ended_at=t.ended_at,
        distance_km=t.distance_km, start_odometer_km=t.start_odometer_km, end_odometer_km=t.end_odometer_km,
        purpose=t.purpose, business=t.business,
        driver_name=t.driver_name, start_address=t.start_address, end_address=t.end_address
    )

@protected.post("/trips", response_model=TripOut)
def create_trip(payload: TripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
    if not veh:
        veh = Vehicle(reg_no=payload.vehicle_reg)
        db.add(veh); db.flush()

    if payload.ended_at is not None and payload.ended_at <= payload.started_at:
        raise HTTPException(400, "ended_at must be after started_at")

    ensure_no_overlap(db, user.id, veh.id, payload.started_at, payload.ended_at)

    dist_km = payload.distance_km
    if dist_km is None and (payload.ended_at is not None):
        dist_km = odo_delta_distance(payload.start_odometer_km, payload.end_odometer_km)

    trip = Trip(
        user_id=user.id,
        vehicle_id=veh.id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        start_odometer_km=payload.start_odometer_km,
        end_odometer_km=payload.end_odometer_km,
        distance_km=dist_km,
        purpose=payload.purpose,
        business=payload.business,
        driver_name=payload.driver_name,
        start_address=payload.start_address,
        end_address=payload.end_address,
    )
    db.add(trip); db.commit(); db.refresh(trip)

    return TripOut(
        id=trip.id, vehicle_reg=veh.reg_no,
        started_at=trip.started_at, ended_at=trip.ended_at,
        distance_km=trip.distance_km,
        start_odometer_km=trip.start_odometer_km,
        end_odometer_km=trip.end_odometer_km,
        purpose=trip.purpose, business=trip.business,
        driver_name=trip.driver_name, start_address=trip.start_address, end_address=trip.end_address
    )

@protected.put("/trips/{trip_id}", response_model=TripOut)
def update_trip(trip_id: int, payload: TripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id==trip_id, Trip.user_id==user.id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")

    veh = db.query(Vehicle).filter(Vehicle.reg_no==payload.vehicle_reg).first()
    if not veh:
        veh = Vehicle(reg_no=payload.vehicle_reg)
        db.add(veh); db.flush()

    if payload.ended_at is not None and payload.ended_at <= payload.started_at:
        raise HTTPException(400, "ended_at must be after started_at")

    ensure_no_overlap(db, user.id, veh.id, payload.started_at, payload.ended_at, exclude_id=trip.id)

    dist_km = payload.distance_km
    if dist_km is None and (payload.ended_at is not None):
        dist_km = odo_delta_distance(payload.start_odometer_km, payload.end_odometer_km)

    trip.user_id = user.id
    trip.vehicle_id = veh.id
    trip.started_at = payload.started_at
    trip.ended_at   = payload.ended_at
    trip.start_odometer_km = payload.start_odometer_km
    trip.end_odometer_km   = payload.end_odometer_km
    trip.distance_km = dist_km if dist_km is not None else trip.distance_km
    trip.purpose = payload.purpose
    trip.business = payload.business
    trip.driver_name = payload.driver_name
    trip.start_address = payload.start_address
    trip.end_address = payload.end_address
    trip.updated_at = datetime.utcnow()

    db.commit(); db.refresh(trip)

    return TripOut(
        id=trip.id,
        vehicle_reg=veh.reg_no,
        started_at=trip.started_at,
        ended_at=trip.ended_at,
        distance_km=trip.distance_km,
        start_odometer_km=trip.start_odometer_km,
        end_odometer_km=trip.end_odometer_km,
        purpose=trip.purpose,
        business=trip.business,
        driver_name=trip.driver_name, start_address=trip.start_address, end_address=trip.end_address
    )

@protected.delete("/trips/{trip_id}")
def delete_trip(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(Trip).filter(Trip.id==trip_id, Trip.user_id==user.id).first()
    if not t:
        raise HTTPException(404, "Trip not found")
    db.delete(t); db.commit()
    return {"status": "deleted"}

@protected.get("/trips", response_model=None)
def list_trips(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    vehicle: Optional[str] = Query(None),
    include_active: bool = Query(True),
):
    q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id == Vehicle.id).filter(Trip.user_id==user.id)
    if vehicle:   q = q.filter(Vehicle.reg_no == vehicle)
    if not include_active:
        q = q.filter(Trip.ended_at.isnot(None))

    res = []
    for t, v in q.order_by(Trip.started_at.desc()).limit(500).all():
        res.append({
            "id": t.id,
            "vehicle_reg": v.reg_no,
            "started_at": t.started_at,
            "ended_at": t.ended_at,
            "distance_km": t.distance_km,
            "start_odometer_km": t.start_odometer_km,
            "end_odometer_km": t.end_odometer_km,
            "purpose": t.purpose,
            "business": t.business,
            "driver_name": t.driver_name,
            "start_address": t.start_address,
            "end_address": t.end_address,
        })

    payload = jsonable_encoder(res)
    response = JSONResponse(content=payload)
    response.headers["Cache-Control"] = "no-store"
    return response

# ----- Templates (per user) -----
@protected.get("/templates", response_model=List[TemplateOut])
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tpls = db.query(TripTemplate).filter(TripTemplate.user_id==user.id).order_by(TripTemplate.name.asc()).all()
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

@protected.post("/templates", response_model=TemplateOut)
def create_template(payload: TemplateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    exists = db.query(TripTemplate).filter(TripTemplate.user_id==user.id, TripTemplate.name == payload.name).first()
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
    db.add(t); db.commit(); db.refresh(t)
    return TemplateOut(
        id=t.id, name=t.name, default_purpose=t.default_purpose,
        business=t.business, default_distance_km=t.default_distance_km,
        default_vehicle_reg=t.default_vehicle_reg,
        default_driver_name=t.default_driver_name,
        default_start_address=t.default_start_address,
        default_end_address=t.default_end_address
    )

@protected.put("/templates/{tpl_id}", response_model=TemplateOut)
def update_template(tpl_id: int, payload: TemplateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(TripTemplate).filter(TripTemplate.id==tpl_id, TripTemplate.user_id==user.id).first()
    if not t:
        raise HTTPException(404, "Template not found")

    if payload.name and payload.name != t.name:
        exists = db.query(TripTemplate).filter(TripTemplate.user_id==user.id, TripTemplate.name == payload.name).first()
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

    db.commit(); db.refresh(t)
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

@protected.delete("/templates/{tpl_id}")
def delete_template(tpl_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(TripTemplate).filter(TripTemplate.id==tpl_id, TripTemplate.user_id==user.id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    db.delete(t); db.commit()
    return {"status": "deleted"}

# ----- Exports (per user) -----
@protected.get("/exports/journal.csv")
def export_csv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    vehicle: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    import csv
    from io import StringIO

    q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id==Vehicle.id).filter(Trip.user_id==user.id)
    if vehicle: q = q.filter(Vehicle.reg_no == vehicle)
    if year:
        q = q.filter(Trip.started_at >= datetime(year,1,1), Trip.started_at < datetime(year+1,1,1))
    q = q.filter(Trip.ended_at.isnot(None))

    output = StringIO(); writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "År","Regnr","Datum","Startadress","Slutadress",
        "Start mätarställning","Slut mätarställning","Antal km","Ärende/Syfte","Förare","Tjänst/Privat"
    ])

    for t, v in q.order_by(Trip.started_at.asc()).all():
        datum = t.started_at.strftime('%Y-%m-%d') if t.started_at else ""
        writer.writerow([
            t.started_at.year if t.started_at else "",
            v.reg_no, datum,
            t.start_address or "",
            t.end_address or "",
            t.start_odometer_km or "", t.end_odometer_km or "",
            t.distance_km or "",
            t.purpose or "",
            t.driver_name or "",
            "Tjänst" if t.business else "Privat",
        ])

    csv_bytes = output.getvalue().encode('utf-8-sig')
    return Response(content=csv_bytes, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=korjournal.csv"})

@protected.get("/exports/journal.pdf")
def export_pdf_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    vehicle: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id==Vehicle.id).filter(Trip.user_id==user.id)
    if vehicle: q = q.filter(Vehicle.reg_no == vehicle)
    if year:
        q = q.filter(Trip.started_at >= datetime(year,1,1), Trip.started_at < datetime(year+1,1,1))
    q = q.filter(Trip.ended_at.isnot(None))

    rows = []
    for t, v in q.order_by(Trip.started_at.asc()).all():
        rows.append({
            "datum": t.started_at.strftime('%Y-%m-%d') if t.started_at else "",
            "start_odo": t.start_odometer_km or "",
            "end_odo": t.end_odometer_km or "",
            "km": t.distance_km or "",
            "start_adress": t.start_address or "",
            "slut_adress": t.end_address or "",
            "syfte": t.purpose or "",
            "tjanst": t.business,
        })

    pdf_bytes = render_journal_pdf(rows)
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=korjournal.pdf"})

# register protected routes
app.include_router(protected)
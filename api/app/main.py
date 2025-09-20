from fastapi import FastAPI, Depends, Query, Response, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime
from typing import Optional, List
import math, httpx, os

from .db import SessionLocal, engine
from .models import Base, Trip, Vehicle, Place, OdometerSnapshot, TripTemplate
from .pdf import render_journal_pdf

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

OSRM_URL = os.getenv("OSRM_URL")

# --- Home Assistant polling config ---
HA_BASE_URL = os.getenv("HA_BASE_URL")          # ex: http://homeassistant.local:8123
HA_TOKEN    = os.getenv("HA_TOKEN")             # Long-Lived Access Token
HA_ENTITY   = os.getenv("HA_ODOMETER_ENTITY")   # ex: sensor.kia_something_odometer

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

async def osrm_distance_km(a_lat, a_lon, b_lat, b_lon) -> Optional[float]:
    if not OSRM_URL:
        return None
    url = f"{OSRM_URL}/route/v1/driving/{a_lon},{a_lat};{b_lon},{b_lat}?overview=false"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            return data["routes"][0]["distance"] / 1000.0
    except Exception:
        return None

from pydantic import BaseModel

class TripIn(BaseModel):
    vehicle_reg: str
    started_at: datetime
    ended_at: datetime
    start_odometer_km: Optional[float] = None
    end_odometer_km: Optional[float] = None
    distance_km: Optional[float] = None
    start_place: Optional[str] = None
    end_place: Optional[str] = None
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None
    purpose: Optional[str] = None
    business: bool = True
    notes: Optional[str] = None

class TripOut(BaseModel):
    id: int
    vehicle_reg: str
    started_at: datetime
    ended_at: datetime
    distance_km: Optional[float]
    purpose: Optional[str]
    business: bool
    class Config:
        from_attributes = True

class OdoIn(BaseModel):
    vehicle_reg: str
    value_km: float
    at: datetime
    source: Optional[str] = None

# ---- Templates ----
class TemplateIn(BaseModel):
    name: str
    default_purpose: Optional[str] = None
    business: bool = True
    default_distance_km: Optional[float] = None
    start_place: Optional[str] = None
    end_place: Optional[str] = None

class TemplateOut(BaseModel):
    id: int
    name: str
    default_purpose: Optional[str]
    business: bool
    default_distance_km: Optional[float]
    start_place: Optional[str]
    end_place: Optional[str]

def ensure_no_overlap(db: Session, vehicle_id: int, start: datetime, end: datetime, exclude_id: Optional[int]=None):
    q = db.query(Trip).filter(Trip.vehicle_id==vehicle_id)
    if exclude_id:
        q = q.filter(Trip.id != exclude_id)
    q = q.filter(
        or_(
            and_(Trip.started_at <= start, Trip.ended_at > start),
            and_(Trip.started_at < end,   Trip.ended_at >= end),
            and_(Trip.started_at >= start, Trip.ended_at <= end),
        )
    )
    if db.query(q.exists()).scalar():
        raise HTTPException(status_code=400, detail="Overlapping trip for the same vehicle")

# ---- Trips CRUD (oförändrat från din senaste version, utom imports) ----
# ... (behåll dina befintliga /trips, /exports, /odometer, /integrations... endpoints) ...

# --- Templates endpoints ---
@app.post("/templates", response_model=TemplateOut)
def create_template(payload: TemplateIn, db: Session = Depends(get_db)):
    # places on-the-fly
    sp = ep = None
    if payload.start_place:
        sp = Place(name=payload.start_place, address=payload.start_place)
        db.add(sp); db.flush()
    if payload.end_place:
        ep = Place(name=payload.end_place, address=payload.end_place)
        db.add(ep); db.flush()

    t = TripTemplate(
        name=payload.name,
        default_purpose=payload.default_purpose,
        business=payload.business,
        default_distance_km=payload.default_distance_km,
        start_place_id=sp.id if sp else None,
        end_place_id=ep.id if ep else None,
    )
    db.add(t); db.commit(); db.refresh(t)
    return TemplateOut(
        id=t.id, name=t.name,
        default_purpose=t.default_purpose,
        business=t.business,
        default_distance_km=t.default_distance_km,
        start_place=t.start_place.address if t.start_place_id else None,
        end_place=t.end_place.address if t.end_place_id else None,
    )

@app.get("/templates", response_model=List[TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    out: List[TemplateOut] = []
    for t in db.query(TripTemplate).order_by(TripTemplate.name).all():
        out.append(TemplateOut(
            id=t.id, name=t.name,
            default_purpose=t.default_purpose,
            business=t.business,
            default_distance_km=t.default_distance_km,
            start_place=t.start_place.address if t.start_place_id else None,
            end_place=t.end_place.address if t.end_place_id else None,
        ))
    return out

class ApplyTemplateIn(BaseModel):
    vehicle_reg: str
    started_at: datetime
    ended_at: datetime
    # tillåt override av template:
    purpose: Optional[str] = None
    distance_km: Optional[float] = None
    business: Optional[bool] = None

@app.post("/templates/{tid}/apply", response_model=TripOut)
async def apply_template(tid: int, payload: ApplyTemplateIn, db: Session = Depends(get_db)):
    tpl = db.query(TripTemplate).get(tid)
    if not tpl:
        raise HTTPException(404, "Template not found")
    # bygg TripIn från template + payload
    trip_in = TripIn(
        vehicle_reg=payload.vehicle_reg,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        purpose=payload.purpose if payload.purpose is not None else tpl.default_purpose,
        business=payload.business if payload.business is not None else tpl.business,
        distance_km=payload.distance_km if payload.distance_km is not None else tpl.default_distance_km,
        start_place=tpl.start_place.address if tpl.start_place_id else None,
        end_place=tpl.end_place.address if tpl.end_place_id else None,
    )
    # återanvänd create_trip-logiken:
    return await create_trip(trip_in, db)

# --- HA polling endpoint (om du inte vill webhooka) ---
class HAPollIn(BaseModel):
    vehicle_reg: str
    entity_id: Optional[str] = None  # override
    at: Optional[datetime] = None

@app.post("/integrations/home-assistant/poll")
async def ha_poll(payload: HAPollIn, db: Session = Depends(get_db)):
    if not (HA_BASE_URL and HA_TOKEN and (HA_ENTITY or payload.entity_id)):
        raise HTTPException(400, "HA_BASE_URL, HA_TOKEN, and HA_ODOMETER_ENTITY (or entity_id) must be set")

    entity = payload.entity_id or HA_ENTITY
    url = f"{HA_BASE_URL}/api/states/{entity}"
    headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=10, verify=False) as client:
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            raise HTTPException(r.status_code, f"HA states fetch failed: {r.text}")
        data = r.json()
        # Home Assistant sensors expose "state" as string
        try:
            value_km = float(data.get("state"))
        except Exception:
            raise HTTPException(500, f"Could not parse odometer state: {data.get('state')}")
        at = payload.at or datetime.utcnow()

    # spara snapshot
    veh = db.query(Vehicle).filter(Vehicle.reg_no==payload.vehicle_reg).first()
    if not veh:
        veh = Vehicle(reg_no=payload.vehicle_reg)
        db.add(veh); db.flush()
    snap = OdometerSnapshot(vehicle_id=veh.id, at=at, value_km=value_km, source="ha-poll")
    db.add(snap); db.commit()
    return {"status": "ok", "value_km": value_km, "entity": entity}

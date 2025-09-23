from fastapi import FastAPI, Depends, Query, Response, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text
from datetime import datetime
from typing import Optional, List, Tuple
import httpx, os, asyncio, json, math
from pydantic import BaseModel

from .db import SessionLocal, engine
from .models import Base, Trip, Vehicle, Place, OdometerSnapshot, TripTemplate, Setting
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

ENV_HA_BASE_URL = os.getenv("HA_BASE_URL")
ENV_HA_TOKEN    = os.getenv("HA_TOKEN")
ENV_HA_ENTITY   = os.getenv("HA_ODOMETER_ENTITY")
ENV_HA_FORCE_DOMAIN  = os.getenv("HA_FORCE_DOMAIN", "kia_uvo")
ENV_HA_FORCE_SERVICE = os.getenv("HA_FORCE_SERVICE", "force_update")
ENV_HA_FORCE_DATA    = os.getenv("HA_FORCE_DATA")

def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()

def get_setting(db: Session, key: str) -> Optional[str]:
  s = db.query(Setting).filter(Setting.key == key).first()
  return s.value if s else None

def set_setting(db: Session, key: str, value: str):
  s = db.query(Setting).filter(Setting.key == key).first()
  now = datetime.utcnow()
  if s:
    s.value = value; s.updated_at = now
  else:
    s = Setting(key=key, value=value, updated_at=now)
    db.add(s)
  db.commit()

def get_ha_config(db: Session) -> Tuple[Optional[str], Optional[str], Optional[str], str, str, Optional[dict]]:
  base = ENV_HA_BASE_URL or get_setting(db, "HA_BASE_URL")
  token = ENV_HA_TOKEN    or get_setting(db, "HA_TOKEN")
  entity= ENV_HA_ENTITY   or get_setting(db, "HA_ODOMETER_ENTITY")
  domain = ENV_HA_FORCE_DOMAIN or get_setting(db, "HA_FORCE_DOMAIN") or "kia_uvo"
  service= ENV_HA_FORCE_SERVICE or get_setting(db, "HA_FORCE_SERVICE") or "force_update"
  data_raw = ENV_HA_FORCE_DATA or get_setting(db, "HA_FORCE_DATA")
  data_json = None
  if data_raw:
    try: data_json = json.loads(data_raw)
    except Exception: data_json = None
  return base, token, entity, domain, service, data_json

def haversine(lat1, lon1, lat2, lon2):
  R = 6371.0
  phi1, phi2 = math.radians(lat1), math.radians(lat2)
  dphi = math.radians(lat2 - lat1)
  dl = math.radians(lon2 - lon1)
  a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
  return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

async def osrm_distance_km(a_lat, a_lon, b_lat, b_lon) -> Optional[float]:
  OSRM_URL = os.getenv("OSRM_URL")
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

# ---- Pydantic modeller ----
class TripIn(BaseModel):
  vehicle_reg: str
  started_at: datetime
  ended_at: Optional[datetime] = None
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
  ended_at: Optional[datetime]
  distance_km: Optional[float]
  start_odometer_km: Optional[float]
  end_odometer_km: Optional[float]
  purpose: Optional[str]
  business: bool
  class Config:
    from_attributes = True

class StartTripIn(BaseModel):
  vehicle_reg: str
  started_at: Optional[datetime] = None
  start_odometer_km: Optional[float] = None
  purpose: Optional[str] = None
  business: bool = True

class FinishTripIn(BaseModel):
  vehicle_reg: Optional[str] = None
  trip_id: Optional[int] = None
  ended_at: Optional[datetime] = None
  end_odometer_km: Optional[float] = None
  distance_km: Optional[float] = None
  purpose: Optional[str] = None
  business: Optional[bool] = None

class OdoIn(BaseModel):
  vehicle_reg: str
  value_km: float
  at: datetime
  source: Optional[str] = None

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
  class Config:
    from_attributes = True

class HAPollIn(BaseModel):
  vehicle_reg: str
  entity_id: Optional[str] = None
  at: Optional[datetime] = None

class HASettingsIn(BaseModel):
  base_url: Optional[str] = None
  token: Optional[str] = None
  entity_id: Optional[str] = None
  force_domain: Optional[str] = None
  force_service: Optional[str] = None
  force_data_json: Optional[dict] = None

def ensure_no_overlap(db: Session, vehicle_id: int, start: datetime, end: Optional[datetime], exclude_id: Optional[int]=None):
  q = db.query(Trip).filter(Trip.vehicle_id==vehicle_id)
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
        and_(Trip.ended_at.is_(None), Trip.started_at <= end)
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

# ---------- Health ----------
@app.get("/health")
def health(db: Session = Depends(get_db)):
  try:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
  except Exception as e:
    print("HEALTHCHECK DB ERROR:", repr(e))
    return JSONResponse({"status": "db_error", "error": str(e)}, status_code=500)

# ---------- Trips: start/finish ----------
@app.post("/trips/start", response_model=TripOut)
def start_trip(payload: StartTripIn, db: Session = Depends(get_db)):
  veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
  if not veh:
    veh = Vehicle(reg_no=payload.vehicle_reg)
    db.add(veh); db.flush()

  existing = db.query(Trip).filter(Trip.vehicle_id==veh.id, Trip.ended_at.is_(None)).first()
  if existing:
    raise HTTPException(400, "Det finns redan en pågående resa för detta fordon")

  started_at = payload.started_at or datetime.utcnow()
  ensure_no_overlap(db, veh.id, started_at, None)

  trip = Trip(
    vehicle_id=veh.id,
    started_at=started_at,
    ended_at=None,
    start_odometer_km=payload.start_odometer_km,
    purpose=payload.purpose,
    business=payload.business,
  )
  db.add(trip); db.commit(); db.refresh(trip)

  return TripOut(
    id=trip.id, vehicle_reg=veh.reg_no, started_at=trip.started_at, ended_at=None,
    distance_km=None, start_odometer_km=trip.start_odometer_km, end_odometer_km=None,
    purpose=trip.purpose, business=trip.business
  )

@app.post("/trips/finish", response_model=TripOut)
def finish_trip(payload: FinishTripIn, db: Session = Depends(get_db)):
  t: Optional[Trip] = None
  if payload.trip_id:
    t = db.query(Trip).get(payload.trip_id)
    if not t: raise HTTPException(404, "Trip not found")
    if t.ended_at is not None: raise HTTPException(400, "Trip already finished")
  else:
    if not payload.vehicle_reg:
      raise HTTPException(400, "vehicle_reg eller trip_id krävs")
    veh = db.query(Vehicle).filter(Vehicle.reg_no==payload.vehicle_reg).first()
    if not veh: raise HTTPException(404, "Vehicle not found")
    t = db.query(Trip).filter(Trip.vehicle_id==veh.id, Trip.ended_at.is_(None)).order_by(Trip.started_at.desc()).first()
    if not t: raise HTTPException(404, "Ingen pågående resa att avsluta")

  ended_at = payload.ended_at or datetime.utcnow()
  ensure_no_overlap(db, t.vehicle_id, t.started_at, ended_at, exclude_id=t.id)

  t.ended_at = ended_at
  if payload.end_odometer_km is not None:
    t.end_odometer_km = payload.end_odometer_km
  if payload.purpose is not None:
    t.purpose = payload.purpose
  if payload.business is not None:
    t.business = payload.business

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
    purpose=t.purpose, business=t.business
  )

# ---------- CRUD ----------
@app.post("/trips", response_model=TripOut)
def create_trip(payload: TripIn, db: Session = Depends(get_db)):
  veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
  if not veh:
    veh = Vehicle(reg_no=payload.vehicle_reg)
    db.add(veh); db.flush()

  if payload.ended_at is not None and payload.ended_at <= payload.started_at:
    raise HTTPException(400, "ended_at must be after started_at")

  ensure_no_overlap(db, veh.id, payload.started_at, payload.ended_at)

  dist_km = payload.distance_km
  if dist_km is None and (payload.ended_at is not None):
    dist_km = odo_delta_distance(payload.start_odometer_km, payload.end_odometer_km)

  trip = Trip(
    vehicle_id=veh.id,
    started_at=payload.started_at,
    ended_at=payload.ended_at,
    start_odometer_km=payload.start_odometer_km,
    end_odometer_km=payload.end_odometer_km,
    distance_km=dist_km,
    purpose=payload.purpose,
    business=payload.business,
    notes=payload.notes,
  )
  db.add(trip); db.commit(); db.refresh(trip)

  return TripOut(
    id=trip.id, vehicle_reg=veh.reg_no,
    started_at=trip.started_at, ended_at=trip.ended_at,
    distance_km=trip.distance_km,
    start_odometer_km=trip.start_odometer_km,
    end_odometer_km=trip.end_odometer_km,
    purpose=trip.purpose, business=trip.business,
  )

@app.put("/trips/{trip_id}", response_model=TripOut)
def update_trip(trip_id: int = Path(...), payload: TripIn = None, db: Session = Depends(get_db)):
  trip = db.query(Trip).get(trip_id)
  if not trip:
    raise HTTPException(404, "Trip not found")

  veh = db.query(Vehicle).filter(Vehicle.reg_no==payload.vehicle_reg).first()
  if not veh:
    veh = Vehicle(reg_no=payload.vehicle_reg)
    db.add(veh); db.flush()

  if payload.ended_at is not None and payload.ended_at <= payload.started_at:
    raise HTTPException(400, "ended_at must be after started_at")

  ensure_no_overlap(db, veh.id, payload.started_at, payload.ended_at, exclude_id=trip.id)

  dist_km = payload.distance_km
  if dist_km is None and (payload.ended_at is not None):
    dist_km = odo_delta_distance(payload.start_odometer_km, payload.end_odometer_km)

  trip.vehicle_id = veh.id
  trip.started_at = payload.started_at
  trip.ended_at   = payload.ended_at
  trip.start_odometer_km = payload.start_odometer_km
  trip.end_odometer_km   = payload.end_odometer_km
  trip.distance_km = dist_km if dist_km is not None else trip.distance_km
  trip.purpose = payload.purpose
  trip.business = payload.business
  trip.notes = payload.notes
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
  )

@app.delete("/trips/{trip_id}")
def delete_trip(trip_id: int, db: Session = Depends(get_db)):
  t = db.query(Trip).get(trip_id)
  if not t:
    raise HTTPException(404, "Trip not found")
  db.delete(t); db.commit()
  return {"status": "deleted"}

@app.get("/trips", response_model=None)
def list_trips(
  db: Session = Depends(get_db),
  vehicle: Optional[str] = Query(None),
  include_active: bool = Query(True),
):
  q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id == Vehicle.id)
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
    })

  payload = jsonable_encoder(res)
  response = JSONResponse(content=payload)
  response.headers["Cache-Control"] = "no-store"
  return response

# ---------- Templates ----------
@app.get("/templates", response_model=List[TemplateOut])
def list_templates(db: Session = Depends(get_db)):
  tpls = db.query(TripTemplate).order_by(TripTemplate.name.asc()).all()
  out = []
  for t in tpls:
    out.append(TemplateOut(
      id=t.id,
      name=t.name,
      default_purpose=t.default_purpose,
      business=t.business,
      default_distance_km=t.default_distance_km,
      start_place=t.start_place.address if t.start_place_id else None,
      end_place=t.end_place.address if t.end_place_id else None,
    ))
  return out

@app.post("/templates", response_model=TemplateOut)
def create_template(payload: TemplateIn, db: Session = Depends(get_db)):
  t = TripTemplate(
    name=payload.name,
    default_purpose=payload.default_purpose,
    business=payload.business,
    default_distance_km=payload.default_distance_km,
  )
  db.add(t); db.commit(); db.refresh(t)
  return TemplateOut(
    id=t.id, name=t.name, default_purpose=t.default_purpose,
    business=t.business, default_distance_km=t.default_distance_km,
    start_place=None, end_place=None
  )

@app.post("/templates/{tpl_id}/apply", response_model=TripOut)
def apply_template(tpl_id: int, payload: TripIn, db: Session = Depends(get_db)):
  tpl = db.query(TripTemplate).get(tpl_id)
  if not tpl: raise HTTPException(404, "Template not found")

  veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
  if not veh:
    veh = Vehicle(reg_no=payload.vehicle_reg)
    db.add(veh); db.flush()

  if payload.ended_at is not None and payload.ended_at <= payload.started_at:
    raise HTTPException(400, "ended_at must be after started_at")
  ensure_no_overlap(db, veh.id, payload.started_at, payload.ended_at)

  dist_km = payload.distance_km
  if dist_km is None and tpl.default_distance_km is not None and payload.ended_at is not None:
    dist_km = tpl.default_distance_km
  if dist_km is None and payload.ended_at is not None:
    dist_km = odo_delta_distance(payload.start_odometer_km, payload.end_odometer_km)

  trip = Trip(
    vehicle_id=veh.id,
    started_at=payload.started_at,
    ended_at=payload.ended_at,
    start_odometer_km=payload.start_odometer_km,
    end_odometer_km=payload.end_odometer_km,
    distance_km=dist_km,
    purpose=payload.purpose or tpl.default_purpose,
    business=payload.business if payload.business is not None else tpl.business,
  )
  db.add(trip); db.commit(); db.refresh(trip)
  return TripOut(
    id=trip.id, vehicle_reg=veh.reg_no,
    started_at=trip.started_at, ended_at=trip.ended_at,
    distance_km=trip.distance_km,
    start_odometer_km=trip.start_odometer_km,
    end_odometer_km=trip.end_odometer_km,
    purpose=trip.purpose, business=trip.business
  )

# ---------- Exports ----------
@app.get("/exports/journal.csv")
def export_csv(
  db: Session = Depends(get_db),
  vehicle: Optional[str] = Query(None),
  year: Optional[int] = Query(None),
):
  import csv
  from io import StringIO

  q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id==Vehicle.id)
  if vehicle: q = q.filter(Vehicle.reg_no == vehicle)
  if year:
    q = q.filter(Trip.started_at >= datetime(year,1,1), Trip.started_at < datetime(year+1,1,1))
  q = q.filter(Trip.ended_at.isnot(None))

  output = StringIO(); writer = csv.writer(output, delimiter=';')
  writer.writerow(["År","Regnr","Datum","Startadress","Slutadress","Start mätarställning","Slut mätarställning","Antal km","Ärende/Syfte","Förare","Tjänst/Privat","Anteckningar"])

  for t, v in q.order_by(Trip.started_at.asc()).all():
    datum = t.started_at.strftime('%Y-%m-%d')
    writer.writerow([
      t.started_at.year if t.started_at else "",
      v.reg_no, datum,
      t.start_place.address if t.start_place_id else "",
      t.end_place.address if t.end_place_id else "",
      t.start_odometer_km or "", t.end_odometer_km or "",
      t.distance_km or "",
      t.purpose or "",
      "",
      "Tjänst" if t.business else "Privat",
      t.notes or "",
    ])

  csv_bytes = output.getvalue().encode('utf-8-sig')
  return Response(content=csv_bytes, media_type="text/csv",
                  headers={"Content-Disposition": "attachment; filename=korjournal.csv"})

@app.get("/exports/journal.pdf")
def export_pdf_endpoint(
  db: Session = Depends(get_db),
  vehicle: Optional[str] = Query(None),
  year: Optional[int] = Query(None),
):
  q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id==Vehicle.id)
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
      "start_adress": t.start_place.address if t.start_place_id else "",
      "slut_adress": t.end_place.address if t.end_place_id else "",
      "syfte": t.purpose or "",
      "tjanst": t.business,
    })

  pdf_bytes = render_journal_pdf(rows)
  return Response(content=pdf_bytes, media_type="application/pdf",
                  headers={"Content-Disposition": "attachment; filename=korjournal.pdf"})

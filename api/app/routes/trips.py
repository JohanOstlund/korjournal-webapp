"""
Trip management routes.
"""
from datetime import datetime
from typing import Optional
import logging

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..db import get_db
from ..models import Trip, Vehicle, User
from ..schemas import TripIn, TripOut, StartTripIn, FinishTripIn
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trips", tags=["trips"])

def ensure_no_overlap(db: Session, user_id: int, vehicle_id: int, start: datetime, end: Optional[datetime], exclude_id: Optional[int] = None):
    """Ensure no overlapping trips for the same user/vehicle."""
    q = db.query(Trip).filter(Trip.user_id == user_id, Trip.vehicle_id == vehicle_id)
    if exclude_id:
        q = q.filter(Trip.id != exclude_id)
    if end is None:
        q = q.filter(Trip.ended_at.is_(None) | and_(Trip.started_at <= start, Trip.ended_at > start))
    else:
        q = q.filter(
            or_(
                and_(Trip.started_at <= start, Trip.ended_at > start),
                and_(Trip.started_at < end, Trip.ended_at >= end),
                and_(Trip.started_at >= start, Trip.ended_at <= end),
                and_(Trip.ended_at.is_(None), Trip.started_at <= end),
            )
        )
    if db.query(q.exists()).scalar():
        raise HTTPException(status_code=400, detail="Overlapping/active trip for the same vehicle")

def odo_delta_distance(start_odo: Optional[float], end_odo: Optional[float]) -> Optional[float]:
    """Calculate distance from odometer readings."""
    if start_odo is None or end_odo is None:
        return None
    d = end_odo - start_odo
    if d < 0:
        return None
    return round(d, 1)

@router.post("/start", response_model=TripOut)
def start_trip(payload: StartTripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Start a new trip."""
    veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
    if not veh:
        veh = Vehicle(reg_no=payload.vehicle_reg)
        db.add(veh)
        db.flush()

    existing = db.query(Trip).filter(Trip.user_id == user.id, Trip.vehicle_id == veh.id, Trip.ended_at.is_(None)).first()
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
    db.add(trip)
    db.commit()
    db.refresh(trip)
    logger.info(f"Trip started: ID={trip.id}, User={user.username}, Vehicle={veh.reg_no}")

    return TripOut(
        id=trip.id, vehicle_reg=veh.reg_no, started_at=trip.started_at, ended_at=None,
        distance_km=None, start_odometer_km=trip.start_odometer_km, end_odometer_km=None,
        purpose=trip.purpose, business=trip.business,
        driver_name=trip.driver_name, start_address=trip.start_address, end_address=trip.end_address
    )

@router.post("/finish", response_model=TripOut)
def finish_trip(payload: FinishTripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Finish an active trip."""
    t: Optional[Trip] = None
    if payload.trip_id:
        t = db.query(Trip).filter(Trip.id == payload.trip_id, Trip.user_id == user.id).first()
        if not t:
            raise HTTPException(404, "Trip not found")
        if t.ended_at is not None:
            raise HTTPException(400, "Trip already finished")
    else:
        if not payload.vehicle_reg:
            raise HTTPException(400, "vehicle_reg eller trip_id krävs")
        veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
        if not veh:
            raise HTTPException(404, "Vehicle not found")
        t = db.query(Trip).filter(Trip.user_id == user.id, Trip.vehicle_id == veh.id, Trip.ended_at.is_(None)).order_by(Trip.started_at.desc()).first()
        if not t:
            raise HTTPException(404, "Ingen pågående resa att avsluta")

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

    db.commit()
    db.refresh(t)
    veh = db.query(Vehicle).get(t.vehicle_id)
    logger.info(f"Trip finished: ID={t.id}, User={user.username}, Distance={t.distance_km}km")

    return TripOut(
        id=t.id, vehicle_reg=veh.reg_no, started_at=t.started_at, ended_at=t.ended_at,
        distance_km=t.distance_km, start_odometer_km=t.start_odometer_km, end_odometer_km=t.end_odometer_km,
        purpose=t.purpose, business=t.business,
        driver_name=t.driver_name, start_address=t.start_address, end_address=t.end_address
    )

@router.post("", response_model=TripOut)
def create_trip(payload: TripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a complete trip."""
    veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
    if not veh:
        veh = Vehicle(reg_no=payload.vehicle_reg)
        db.add(veh)
        db.flush()

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
    db.add(trip)
    db.commit()
    db.refresh(trip)
    logger.info(f"Trip created: ID={trip.id}, User={user.username}")

    return TripOut(
        id=trip.id, vehicle_reg=veh.reg_no,
        started_at=trip.started_at, ended_at=trip.ended_at,
        distance_km=trip.distance_km,
        start_odometer_km=trip.start_odometer_km,
        end_odometer_km=trip.end_odometer_km,
        purpose=trip.purpose, business=trip.business,
        driver_name=trip.driver_name, start_address=trip.start_address, end_address=trip.end_address
    )

@router.put("/{trip_id}", response_model=TripOut)
def update_trip(trip_id: int, payload: TripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update an existing trip."""
    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")

    veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
    if not veh:
        veh = Vehicle(reg_no=payload.vehicle_reg)
        db.add(veh)
        db.flush()

    if payload.ended_at is not None and payload.ended_at <= payload.started_at:
        raise HTTPException(400, "ended_at must be after started_at")

    ensure_no_overlap(db, user.id, veh.id, payload.started_at, payload.ended_at, exclude_id=trip.id)

    dist_km = payload.distance_km
    if dist_km is None and (payload.ended_at is not None):
        dist_km = odo_delta_distance(payload.start_odometer_km, payload.end_odometer_km)

    trip.user_id = user.id
    trip.vehicle_id = veh.id
    trip.started_at = payload.started_at
    trip.ended_at = payload.ended_at
    trip.start_odometer_km = payload.start_odometer_km
    trip.end_odometer_km = payload.end_odometer_km
    trip.distance_km = dist_km if dist_km is not None else trip.distance_km
    trip.purpose = payload.purpose
    trip.business = payload.business
    trip.driver_name = payload.driver_name
    trip.start_address = payload.start_address
    trip.end_address = payload.end_address
    trip.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(trip)
    logger.info(f"Trip updated: ID={trip.id}, User={user.username}")

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

@router.delete("/{trip_id}")
def delete_trip(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a trip."""
    t = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
    if not t:
        raise HTTPException(404, "Trip not found")
    db.delete(t)
    db.commit()
    logger.info(f"Trip deleted: ID={trip_id}, User={user.username}")
    return {"status": "deleted"}

@router.get("", response_model=None)
def list_trips(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    vehicle: Optional[str] = Query(None),
    include_active: bool = Query(True),
):
    """List all trips for current user."""
    q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id == Vehicle.id).filter(Trip.user_id == user.id)
    if vehicle: q = q.filter(Vehicle.reg_no == vehicle)
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

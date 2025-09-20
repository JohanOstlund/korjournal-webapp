from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="driver")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    reg_no: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    make: Mapped[Optional[str]] = mapped_column(String(80))
    model: Mapped[Optional[str]] = mapped_column(String(80))
    year: Mapped[Optional[int]] = mapped_column(Integer)

class Place(Base):
    __tablename__ = "places"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(120))
    address: Mapped[Optional[str]] = mapped_column(String(255))
    lat: Mapped[Optional[float]]
    lon: Mapped[Optional[float]]

class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime] = mapped_column(DateTime)

    start_odometer_km: Mapped[Optional[float]] = mapped_column(Float)
    end_odometer_km: Mapped[Optional[float]] = mapped_column(Float)
    distance_km: Mapped[Optional[float]] = mapped_column(Float)

    start_place_id: Mapped[Optional[int]] = mapped_column(ForeignKey("places.id"))
    end_place_id: Mapped[Optional[int]] = mapped_column(ForeignKey("places.id"))

    purpose: Mapped[Optional[str]] = mapped_column(String(255))
    business: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(String(1000))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    vehicle: Mapped["Vehicle"] = relationship()
    start_place: Mapped[Optional["Place"]] = relationship(foreign_keys=[start_place_id])
    end_place: Mapped[Optional["Place"]] = relationship(foreign_keys=[end_place_id])

class OdometerSnapshot(Base):
    __tablename__ = "odometer_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    at: Mapped[datetime] = mapped_column(DateTime)
    value_km: Mapped[float] = mapped_column(Float)
    source: Mapped[Optional[str]] = mapped_column(String(50))  # 'kia_uvo','manual','ha'

class TripTemplate(Base):
    __tablename__ = "trip_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    default_purpose: Mapped[Optional[str]] = mapped_column(String(255))
    business: Mapped[bool] = mapped_column(Boolean, default=True)
    default_distance_km: Mapped[Optional[float]] = mapped_column(Float)
    start_place_id: Mapped[Optional[int]] = mapped_column(ForeignKey("places.id"))
    end_place_id: Mapped[Optional[int]] = mapped_column(ForeignKey("places.id"))
    start_place: Mapped[Optional["Place"]] = relationship(foreign_keys=[start_place_id])
    end_place:   Mapped[Optional["Place"]] = relationship(foreign_keys=[end_place_id])

class Setting(Base):
    """
    Enkel key/value-lagring för inställningar (t.ex. HA_BASE_URL, HA_TOKEN, HA_ENTITY).
    Token returneras aldrig i klartext av API:t.
    """
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(String(4096))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

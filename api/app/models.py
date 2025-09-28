from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(190), unique=True, nullable=False)
    password_hash = Column(String(190), nullable=False)

    # backrefs:
    # trips, templates, ha_settings

class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True)
    reg_no = Column(String(32), unique=True, nullable=False, index=True)

class Place(Base):
    __tablename__ = "places"
    id = Column(Integer, primary_key=True)
    address = Column(Text, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)

class OdometerSnapshot(Base):
    __tablename__ = "odometer_snapshots"
    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    at = Column(DateTime, nullable=False, default=datetime.utcnow)
    value_km = Column(Float, nullable=False)

class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True)

    # NEW: ägare av resan
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False)
    ended_at   = Column(DateTime, nullable=True)

    start_place_id = Column(Integer, ForeignKey("places.id"), nullable=True)
    end_place_id   = Column(Integer, ForeignKey("places.id"), nullable=True)

    start_odometer_km = Column(Float, nullable=True)
    end_odometer_km   = Column(Float, nullable=True)
    distance_km       = Column(Float, nullable=True)

    purpose  = Column(Text, nullable=True)
    business = Column(Boolean, nullable=False, default=True)

    driver_name  = Column(String(190), nullable=True)
    start_address = Column(Text, nullable=True)
    end_address   = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    vehicle = relationship("Vehicle")
    start_place = relationship("Place", foreign_keys=[start_place_id])
    end_place   = relationship("Place", foreign_keys=[end_place_id])
    user = relationship("User", backref="trips")

    Index("ix_trips_user_vehicle_started", user_id, vehicle_id, started_at)

class TripTemplate(Base):
    __tablename__ = "trip_templates"
    id = Column(Integer, primary_key=True)

    # NEW: ägare av mallen
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    name = Column(String(190), nullable=False)
    default_purpose = Column(Text, nullable=True)
    business = Column(Boolean, nullable=False, default=True)
    default_distance_km = Column(Float, nullable=True)
    default_vehicle_reg = Column(String(64), nullable=True)
    default_driver_name = Column(String(190), nullable=True)
    default_start_address = Column(Text, nullable=True)
    default_end_address   = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", backref="templates")

    __table_args__ = (
        # Unik mall per användare (namn)
        UniqueConstraint("user_id", "name", name="uq_template_user_name"),
    )

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(190), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class HASetting(Base):
    __tablename__ = "ha_settings"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    base_url = Column(Text, nullable=True)
    token = Column(Text, nullable=True)  # visas aldrig i GET-svar
    odometer_entity = Column(String(255), nullable=True)

    force_domain  = Column(String(255), nullable=True)
    force_service = Column(String(255), nullable=True)
    force_data_json = Column(Text, nullable=True)

    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", backref="ha_settings")
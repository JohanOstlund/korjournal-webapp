from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True)
    reg_no = Column(String(32), unique=True, index=True, nullable=False)
    trips = relationship("Trip", back_populates="vehicle")
    odometer_snaps = relationship("OdometerSnapshot", back_populates="vehicle")

class Place(Base):
    __tablename__ = "places"
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    address = Column(Text)
    lat = Column(Float)
    lon = Column(Float)

class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)

    started_at = Column(DateTime, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=True, index=True)  # NULL = pågående

    start_odometer_km = Column(Float)
    end_odometer_km = Column(Float)
    distance_km = Column(Float)

    start_place_id = Column(Integer, ForeignKey("places.id"))
    end_place_id = Column(Integer, ForeignKey("places.id"))

    purpose = Column(String(255))
    business = Column(Boolean, default=True)

    # Nya fria fält som UI/CSV använder
    driver_name = Column(String(255), nullable=True)
    start_address = Column(String(255), nullable=True)
    end_address   = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    vehicle = relationship("Vehicle", back_populates="trips")
    start_place = relationship("Place", foreign_keys=[start_place_id])
    end_place = relationship("Place", foreign_keys=[end_place_id])

class OdometerSnapshot(Base):
    __tablename__ = "odometer_snaps"
    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True, nullable=False)
    at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    value_km = Column(Float, nullable=False)
    source = Column(String(64))
    vehicle = relationship("Vehicle", back_populates="odometer_snaps")

class TripTemplate(Base):
    __tablename__ = "trip_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False, unique=True)

    # som tidigare
    default_purpose = Column(String(255))
    business = Column(Boolean, default=True)   # True = tjänst, False = privat
    default_distance_km = Column(Float)

    # platsrelationer (kan användas senare)
    start_place_id = Column(Integer, ForeignKey("places.id"))
    end_place_id = Column(Integer, ForeignKey("places.id"))

    # NYTT: egna defaultfält som UI vill ha
    default_vehicle_reg = Column(String(32))
    default_driver_name = Column(String(255))
    default_start_address = Column(String(255))
    default_end_address   = Column(String(255))

    start_place = relationship("Place", foreign_keys=[start_place_id])
    end_place = relationship("Place", foreign_keys=[end_place_id])

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

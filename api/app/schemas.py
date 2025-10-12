"""
Pydantic schemas for request/response models.
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# ===== Auth Schemas =====
class LoginIn(BaseModel):
    username: str
    password: str

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

# ===== User Schemas =====
class UserOut(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True

class CreateUserIn(BaseModel):
    username: str
    password: str

# ===== Trip Schemas =====
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

# ===== Template Schemas =====
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

# ===== HA Integration Schemas =====
class HAPollIn(BaseModel):
    vehicle_reg: str
    entity_id: Optional[str] = None
    at: Optional[datetime] = None

# ===== Settings Schemas =====
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

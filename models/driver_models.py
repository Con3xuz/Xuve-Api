from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class DriverRegister(BaseModel):
    user_id: str
    vehicle_type: str  # moto, taxi, bus, encava, cisterna, flete
    is_owner: bool  # true = dueño, false = avance
    cedula_url: Optional[str] = None
    license_url: Optional[str] = None
    medical_card_url: Optional[str] = None
    owner_cedula: Optional[str] = None
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    plate_number: str
    vehicle_brand: str
    vehicle_model: str


class Driver(BaseModel):
    model_config = ConfigDict(extra="ignore")
    driver_id: str
    user_id: str
    vehicle_type: str
    is_owner: bool
    status: str  # pending, approved, blocked
    is_online: bool = False
    daily_toll_paid: bool = False
    cedula_url: Optional[str] = None
    license_url: Optional[str] = None
    medical_card_url: Optional[str] = None
    owner_cedula: Optional[str] = None
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    plate_number: str
    vehicle_brand: str
    vehicle_model: str
    created_at: datetime

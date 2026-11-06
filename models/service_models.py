from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ServiceType(str, Enum):
    RIDE = "ride"
    DELIVERY = "delivery"
    GENERAL = "general"

class ServiceStatus(str, Enum):
    PENDING = "pending"
    MATCHING = "matching"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Location(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None

class ServiceRequest(BaseModel):
    service_type: str  # movilidad, ruta_fija, carga_gas, market
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    pickup_address: Optional[str] = None
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None
    dropoff_address: Optional[str] = None
    vehicle_preference: Optional[str] = None
    payment_method: Optional[str] = None  # efectivo, pago_movil, wallet
    estimated_fare: Optional[float] = None
    route_id: Optional[str] = None
    notes: Optional[str] = None

class Service(BaseModel):
    model_config = ConfigDict(extra="ignore")
    service_id: str
    user_id: str
    driver_id: Optional[str] = None
    service_type: str
    status: str  # pending, accepted, in_progress, completed, cancelled
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None
    fare: float = 0.0
    commission: float = 0.0
    created_at: datetime

class ProviderAvailability(BaseModel):
    provider_id: str
    location: Location
    service_types: List[ServiceType]
    is_available: bool = True
    last_updated: datetime

class MatchResult(BaseModel):
    service_id: str
    provider_id: str
    distance_km: float
    estimated_time_min: int

class RatingCreate(BaseModel):
    service_id: str
    rating: int  # 1-5 stars
    comment: Optional[str] = None


class Message(BaseModel):
    message_id: str
    service_id: str
    sender_id: str
    sender_name: str
    content: str
    message_type: str = "text"  # text, image, location
    created_at: datetime

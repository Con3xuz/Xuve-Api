from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: str
    service_id: str
    sender_id: str
    sender_role: str
    content: str
    message_type: str  # text, audio, image
    created_at: datetime


class ChatMessageCreate(BaseModel):
    service_id: str
    content: str
    message_type: str = "text"


class FixedRoute(BaseModel):
    model_config = ConfigDict(extra="ignore")
    route_id: str
    name: str
    description: str
    vehicle_type: str  # bus, encava
    fare_usd: float
    waypoints: List[dict]  # [{lat, lng, name}]
    schedule: str
    is_active: bool = True

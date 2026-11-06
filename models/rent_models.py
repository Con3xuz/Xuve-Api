from pydantic import BaseModel
from typing import Optional


class RentVehicleCreate(BaseModel):
    brand: str
    model: str
    year: int = 2020
    color: Optional[str] = None
    plate_number: Optional[str] = None
    daily_rate: float
    deposit_amount: float = 0
    location: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None

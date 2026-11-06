from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime


class MarketProduct(BaseModel):
    model_config = ConfigDict(extra="ignore")
    product_id: str
    store_id: str
    name: str
    description: str
    price_usd: float
    category: str  # comida, supermercado, farmacia
    image_url: Optional[str] = None
    available: bool = True


class MarketStore(BaseModel):
    model_config = ConfigDict(extra="ignore")
    store_id: str
    name: str
    category: str
    address: str
    lat: float
    lng: float
    image_url: Optional[str] = None
    rating: float = 5.0
    is_active: bool = True


class CartItem(BaseModel):
    product_id: str
    quantity: int


class OrderCreate(BaseModel):
    store_id: str
    items: List[CartItem]
    delivery_lat: float
    delivery_lng: float
    delivery_address: str


class Order(BaseModel):
    model_config = ConfigDict(extra="ignore")
    order_id: str
    user_id: str
    store_id: str
    driver_id: Optional[str] = None
    items: List[dict]
    total_usd: float
    delivery_fee: float = 2.0
    commission: float = 0.0
    status: str  # pending, preparing, in_transit, delivered, cancelled
    delivery_lat: float
    delivery_lng: float
    delivery_address: str
    created_at: datetime


class ComercialRegister(BaseModel):
    store_name: str
    category: str  # restaurante, farmacia, supermercado, encomiendas
    address: str
    phone: str
    description: Optional[str] = None
    logo_url: Optional[str] = None


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    category: str = "comida"
    image_url: Optional[str] = None
    available: bool = True

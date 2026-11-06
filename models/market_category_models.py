"""
Modelos para Categorías de Comercios

Sistema de categorías para socios comerciales que permite:
- Seleccionar una categoría de negocio predefinida
- Dashboard personalizado según la categoría
- Organización en el marketplace
"""

from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class BusinessCategory(str, Enum):
    """Categorías disponibles para comercios"""

    RESTAURANTE = "restaurante"
    COMIDA_RAPIDA = "comida_rapida"
    PANADERIA = "panaderia"
    FARMACIA = "farmacia"
    MINIMARKET = "minimarket"
    SUPERMERCADO = "supermercado"
    FERRETERIA = "ferreteria"
    TECNOLOGIA = "tecnologia"
    ROPA = "ropa"
    BELLEZA = "belleza"
    MASCOTAS = "mascotas"
    LICORERIA = "licoreria"
    VIVERES = "viveres"
    OTROS = "otros"


# Configuración visual por categoría
CATEGORY_CONFIG = {
    BusinessCategory.RESTAURANTE: {
        "icon": "utensils",
        "color": "#F97316",
        "label": "Restaurante",
        "emoji": "🍽️",
    },
    BusinessCategory.COMIDA_RAPIDA: {
        "icon": "burger",
        "color": "#EF4444",
        "label": "Comida Rápida",
        "emoji": "🍔",
    },
    BusinessCategory.PANADERIA: {
        "icon": "cake",
        "color": "#F59E0B",
        "label": "Panadería",
        "emoji": "🥐",
    },
    BusinessCategory.FARMACIA: {
        "icon": "pill",
        "color": "#10B981",
        "label": "Farmacia",
        "emoji": "💊",
    },
    BusinessCategory.MINIMARKET: {
        "icon": "store",
        "color": "#3B82F6",
        "label": "Minimarket",
        "emoji": "🏪",
    },
    BusinessCategory.SUPERMERCADO: {
        "icon": "shopping-cart",
        "color": "#6366F1",
        "label": "Supermercado",
        "emoji": "🛒",
    },
    BusinessCategory.FERRETERIA: {
        "icon": "wrench",
        "color": "#71717A",
        "label": "Ferretería",
        "emoji": "🔧",
    },
    BusinessCategory.TECNOLOGIA: {
        "icon": "laptop",
        "color": "#8B5CF6",
        "label": "Tecnología",
        "emoji": "💻",
    },
    BusinessCategory.ROPA: {
        "icon": "shirt",
        "color": "#EC4899",
        "label": "Ropa y Accesorios",
        "emoji": "👕",
    },
    BusinessCategory.BELLEZA: {
        "icon": "sparkles",
        "color": "#F472B6",
        "label": "Belleza y Cuidado",
        "emoji": "💄",
    },
    BusinessCategory.MASCOTAS: {
        "icon": "paw",
        "color": "#84CC16",
        "label": "Mascotas",
        "emoji": "🐾",
    },
    BusinessCategory.LICORERIA: {
        "icon": "wine",
        "color": "#A855F7",
        "label": "Licorería",
        "emoji": "🍷",
    },
    BusinessCategory.VIVERES: {
        "icon": "package",
        "color": "#22C55E",
        "label": "Víveres",
        "emoji": "📦",
    },
    BusinessCategory.OTROS: {
        "icon": "building",
        "color": "#94A3B8",
        "label": "Otros",
        "emoji": "🏢",
    },
}


class StoreProfileCreate(BaseModel):
    """Crear/actualizar perfil de tienda con categoría"""

    store_name: str
    category: BusinessCategory
    description: Optional[str] = None
    address: str
    phone: str
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    opening_hours: Optional[str] = None  # Ej: "8:00 - 20:00"
    delivery_available: bool = True
    pickup_available: bool = True
    min_order_amount: Optional[float] = None


class StoreProfile(BaseModel):
    """Perfil completo de tienda"""

    store_id: str
    user_id: str
    store_name: str
    category: BusinessCategory
    category_config: dict  # Icon, color, label
    description: Optional[str] = None
    address: str
    phone: str
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    opening_hours: Optional[str] = None
    delivery_available: bool = True
    pickup_available: bool = True
    min_order_amount: Optional[float] = None
    is_open: bool = True
    avg_rating: float = 5.0
    total_orders: int = 0
    created_at: str


class CategoryListResponse(BaseModel):
    """Respuesta con lista de categorías disponibles"""

    categories: List[dict]

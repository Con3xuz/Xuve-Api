"""
Rutas para Categorías de Comercios

Gestiona la selección de categoría y perfil de los socios comerciales.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional
from datetime import datetime, timezone
import uuid

from utils.database import db
from utils.auth import get_current_user
from models.market_category_models import (
    BusinessCategory,
    CATEGORY_CONFIG,
    StoreProfileCreate,
)

router = APIRouter(prefix="/comercial", tags=["Comercial Categories"])


@router.get("/categories")
async def get_all_categories():
    """Obtener todas las categorías disponibles para comercios"""
    categories = []
    for cat in BusinessCategory:
        config = CATEGORY_CONFIG.get(cat, {})
        categories.append(
            {
                "id": cat.value,
                "label": config.get("label", cat.value),
                "icon": config.get("icon", "building"),
                "color": config.get("color", "#94A3B8"),
                "emoji": config.get("emoji", "🏢"),
            }
        )
    return {"categories": categories}


@router.post("/profile/setup")
async def setup_store_profile(
    data: StoreProfileCreate, user: dict = Depends(get_current_user)
):
    """Crear o actualizar el perfil de la tienda con categoría"""
    if user["role"] != "socio_comercial" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol socio_comercial")

    # Verificar si ya existe
    existing = await db.store_profiles.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )

    category_config = CATEGORY_CONFIG.get(data.category, {})

    store_data = {
        "user_id": user["user_id"],
        "store_name": data.store_name,
        "category": data.category.value,
        "category_config": {
            "icon": category_config.get("icon", "building"),
            "color": category_config.get("color", "#94A3B8"),
            "label": category_config.get("label", data.category.value),
            "emoji": category_config.get("emoji", "🏢"),
        },
        "description": data.description,
        "address": data.address,
        "phone": data.phone,
        "logo_url": data.logo_url,
        "banner_url": data.banner_url,
        "opening_hours": data.opening_hours,
        "delivery_available": data.delivery_available,
        "pickup_available": data.pickup_available,
        "min_order_amount": data.min_order_amount,
        "is_open": True,
        "avg_rating": 5.0,
        "total_orders": 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if existing:
        # Update
        await db.store_profiles.update_one(
            {"user_id": user["user_id"]}, {"$set": store_data}
        )
        store_data["store_id"] = existing["store_id"]
        return {"message": "Perfil actualizado", "profile": store_data}
    else:
        # Create
        store_id = f"store_{uuid.uuid4().hex[:12]}"
        store_data["store_id"] = store_id
        store_data["created_at"] = datetime.now(timezone.utc).isoformat()

        await db.store_profiles.insert_one(store_data)

        if "_id" in store_data:
            del store_data["_id"]

        return {"message": "Perfil creado", "profile": store_data}


@router.get("/profile")
async def get_store_profile(user: dict = Depends(get_current_user)):
    """Obtener el perfil de mi tienda"""
    profile = await db.store_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0})

    if not profile:
        raise HTTPException(
            status_code=404, detail="Perfil no encontrado. Configura tu tienda primero."
        )

    return profile


@router.patch("/profile/toggle-open")
async def toggle_store_open(user: dict = Depends(get_current_user)):
    """Alternar estado abierto/cerrado de la tienda"""
    profile = await db.store_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0})

    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    new_status = not profile.get("is_open", True)

    await db.store_profiles.update_one(
        {"user_id": user["user_id"]}, {"$set": {"is_open": new_status}}
    )

    return {"is_open": new_status}


@router.get("/stores/by-category/{category}")
async def get_stores_by_category(category: str):
    """Obtener tiendas por categoría (público)"""
    stores = await db.store_profiles.find(
        {"category": category, "is_open": True}, {"_id": 0}
    ).to_list(50)

    return stores


@router.get("/stores/all")
async def get_all_stores(category: Optional[str] = None):
    """Obtener todas las tiendas (público)"""
    query = {"is_open": True}
    if category:
        query["category"] = category

    stores = await db.store_profiles.find(query, {"_id": 0}).to_list(100)

    return stores

"""Controlador de comercial_category - Validaciones y lógica de negocio."""
from models import *
"""
Rutas para Categorías de Comercios

Gestiona la selección de categoría y perfil de los socios comerciales.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional
from datetime import datetime, timezone
import uuid

from models import db
from utils.auth import get_current_user
from controllers.validators import (
    StoreProfileCreate,
)



async def get_all_categories():
    """Obtener todas las categorías disponibles para comercios (desde la BD)"""
    rows = await BusinessCategoryModel.list_active()
    return {
        "categories": [
            {
                "id": r["slug"],
                "label": r["label"],
                "icon": r["icon"],
                "color": r["color"],
                "emoji": r["emoji"],
            }
            for r in rows
        ]
    }


async def setup_store_profile(
    data: StoreProfileCreate, user: dict = Depends(get_current_user)
):
    """Crear o actualizar el perfil de la tienda con categoría"""
    if user["role"] != "socio_comercial" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol socio_comercial")

    # Verificar si ya existe
    existing = await StoreProfileModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )

    category_config = await BusinessCategoryModel.find_by_slug(data.category)
    if not category_config:
        raise HTTPException(status_code=400, detail="Categoría de comercio inválida")

    store_data = {
        "user_id": user["user_id"],
        "store_name": data.store_name,
        "category": data.category,
        "category_config": {
            "icon": category_config["icon"],
            "color": category_config["color"],
            "label": category_config["label"],
            "emoji": category_config["emoji"],
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
        await StoreProfileModel.update_one(
            {"user_id": user["user_id"]}, {"$set": store_data}
        )
        store_data["store_id"] = existing["store_id"]
        return {"message": "Perfil actualizado", "profile": store_data}
    else:
        # Create
        store_id = f"store_{uuid.uuid4().hex[:12]}"
        store_data["store_id"] = store_id
        store_data["created_at"] = datetime.now(timezone.utc).isoformat()

        await StoreProfileModel.insert_one(store_data)
        await SocioComercialModel.update_one(
            {"user_id": user["user_id"]},
            {
                "$set": {
                    "comercial_id": store_id,
                    "user_id": user["user_id"],
                    "business_name": data.store_name,
                    "category": data.category,
                    "address": data.address,
                    "phone": data.phone,
                    "description": data.description,
                    "status": "approved",
                    "is_open": True,
                }
            },
            upsert=True,
        )

        if "_id" in store_data:
            del store_data["_id"]

        return {"message": "Perfil creado", "profile": store_data}


async def get_store_profile(user: dict = Depends(get_current_user)):
    """Obtener el perfil de mi tienda"""
    profile = await StoreProfileModel.find_one({"user_id": user["user_id"]}, {"_id": 0})

    if not profile:
        raise HTTPException(
            status_code=404, detail="Perfil no encontrado. Configura tu tienda primero."
        )

    return profile


async def toggle_store_open(user: dict = Depends(get_current_user)):
    """Alternar estado abierto/cerrado de la tienda"""
    profile = await StoreProfileModel.find_one({"user_id": user["user_id"]}, {"_id": 0})

    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    new_status = not profile.get("is_open", True)

    await StoreProfileModel.update_one(
        {"user_id": user["user_id"]}, {"$set": {"is_open": new_status}}
    )

    return {"is_open": new_status}


async def get_stores_by_category(category: str):
    """Obtener tiendas por categoría (público)"""
    stores = await StoreProfileModel.find(
        {"category": category, "is_open": True}, {"_id": 0}
    ).to_list(50)

    return stores


async def get_all_stores(category: Optional[str] = None):
    """Obtener todas las tiendas (público)"""
    query = {"is_open": True}
    if category:
        query["category"] = category

    stores = await StoreProfileModel.find(query, {"_id": 0}).to_list(100)

    return stores

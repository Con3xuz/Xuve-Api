"""Controlador de socio - Validaciones y lógica de negocio."""
from models import *
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import datetime, timezone
import uuid

from models import db
from utils.financial_config import get_setting, get_activation_fee, get_min_balance_to_connect
from utils.auth import get_current_user
from controllers.validators import (
    CONDUCTOR_VEHICLE_TYPES,
    REPARTIDOR_VEHICLE_TYPES,
    SocioConductorRegister,
    SocioRepartidorRegister,
)
from controllers.validators import ComercialRegister, ProductCreate
from controllers.validators import (
    TransactionType,
)



# ==================== SOCIO CONDUCTOR ENDPOINTS ====================


async def register_socio_conductor(
    data: SocioConductorRegister, user: dict = Depends(get_current_user)
):
    """Registrar como Socio Conductor (Movilidad Urbana)"""
    if data.vehicle_type not in CONDUCTOR_VEHICLE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de vehículo inválido. Opciones: {CONDUCTOR_VEHICLE_TYPES}",
        )

    existing = await SocioConductorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya tienes un perfil de Socio Conductor"
        )

    conductor_doc = {
        "socio_id": f"conductor_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "vehicle_type": data.vehicle_type,
        "status": "pending_kyc",
        "is_online": False,
        "daily_toll_paid": False,
        "current_location": None,
        "kyc": {
            "cedula_url": data.cedula_url,
            "cedula_number": data.cedula_number,
            "license_url": data.license_url,
            "license_category": data.license_category,
            "medical_card_url": data.medical_card_url,
            "circulation_card_url": data.circulation_card_url,
            "rcv_insurance_url": data.rcv_insurance_url,
        },
        "vehicle": {
            "plate_number": data.plate_number,
            "brand": data.vehicle_brand,
            "model": data.vehicle_model,
            "year": data.vehicle_year,
            "color": data.vehicle_color,
            "photo_url": data.vehicle_photo_url,
        },
        "taxi_info": (
            {
                "line_name": data.taxi_line_name,
                "permit": data.taxi_line_permit,
            }
            if data.vehicle_type == "taxi_linea"
            else None
        ),
        "total_trips": 0,
        "total_earnings": 0.0,
        "avg_rating": 5.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await SocioConductorModel.insert_one(conductor_doc)

    if user.get("role") not in ["admin"]:
        await UserModel.update_one(
            {"user_id": user["user_id"]},
            {
                "$set": {
                    "role": "socio_conductor",
                    "sub_role": data.vehicle_type,
                    "kyc_status": "pending",
                }
            },
        )

    if "_id" in conductor_doc:
        del conductor_doc["_id"]

    return {
        "message": "Registro de Socio Conductor enviado. Pendiente de validación KYC.",
        "socio": conductor_doc,
    }


async def get_socio_conductor_profile(user: dict = Depends(get_current_user)):
    """Obtener perfil de Socio Conductor"""
    socio = await SocioConductorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Conductor"
        )
    return socio


async def socio_conductor_go_online(
    lat: float, lng: float, user: dict = Depends(get_current_user)
):
    """
    Conectarse como Socio Conductor.

    GUARDS DE CONEXIÓN:
    1. El perfil debe estar aprobado (status = 'approved')
    2. El fee de activación debe estar pagado (activation_fee_paid = True)
    3. El saldo disponible debe ser >= $1.00
    """
    socio = await SocioConductorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Conductor"
        )

    # Guard 1: Verificar aprobación
    if socio["status"] != "approved":
        raise HTTPException(status_code=403, detail="Tu perfil aún no ha sido aprobado")

    # Guard 2: Verificar fee de activación pagado
    if not socio.get("activation_fee_paid", False):
        raise HTTPException(
            status_code=403,
            detail=f"Debes pagar el fee de activación (${(await get_activation_fee()):.2f}). Recarga tu billetera con al menos $5.00 y contacta al administrador.",
        )

    # Guard 3: Verificar saldo mínimo
    wallet_user = await UserModel.find_one({"user_id": user["user_id"]}, {"_id": 0})
    available = wallet_user.get("wallet_balance", 0) - wallet_user.get("wallet_held", 0)

    if available < (await get_min_balance_to_connect()):
        raise HTTPException(
            status_code=403,
            detail=f"Saldo insuficiente para conectarte. Requieres al menos ${(await get_min_balance_to_connect()):.2f}. Tu saldo disponible: ${available:.2f}. Por favor recarga tu billetera.",
        )

    # Cobrar peaje diario (si no se ha pagado hoy)
    toll_amount = await get_setting("toll_moto" if socio["vehicle_type"] == "mototaxi" else "toll_others")
    toll_paid_now = 0

    if not socio.get("daily_toll_paid"):
        if available < toll_amount:
            raise HTTPException(
                status_code=400,
                detail=f"Saldo insuficiente para peaje diario (${toll_amount}). Disponible: ${available:.2f}",
            )

        await UserModel.update_one(
            {"user_id": user["user_id"]}, {"$inc": {"wallet_balance": -toll_amount}}
        )

        await TransactionModel.insert_one(
            {
                "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
                "user_id": user["user_id"],
                "amount_usd": -toll_amount,
                "type": TransactionType.TOLL.value,
                "status": "completed",
                "description": f"Peaje diario - {socio['vehicle_type']}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        await SocioConductorModel.update_one(
            {"socio_id": socio["socio_id"]}, {"$set": {"daily_toll_paid": True}}
        )
        toll_paid_now = toll_amount

    # Conectar al radar
    await SocioConductorModel.update_one(
        {"socio_id": socio["socio_id"]},
        {
            "$set": {
                "is_online": True,
                "current_location": {
                    "lat": lat,
                    "lng": lng,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            }
        },
    )

    return {
        "message": "Estás en línea",
        "toll_paid": toll_paid_now,
        "current_balance": available - toll_paid_now,
    }


async def socio_conductor_go_offline(user: dict = Depends(get_current_user)):
    """Desconectarse como Socio Conductor"""
    result = await SocioConductorModel.update_one(
        {"user_id": user["user_id"]}, {"$set": {"is_online": False}}
    )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Conductor"
        )
    return {"message": "Estás desconectado"}


async def update_conductor_location(
    lat: float, lng: float, user: dict = Depends(get_current_user)
):
    """Actualizar ubicación del conductor"""
    await SocioConductorModel.update_one(
        {"user_id": user["user_id"], "is_online": True},
        {
            "$set": {
                "current_location": {
                    "lat": lat,
                    "lng": lng,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        },
    )
    return {"message": "Ubicación actualizada"}


async def get_nearby_conductors(
    lat: float, lng: float, vehicle_type: Optional[str] = None
):
    """Obtener conductores cercanos (para usuarios)"""
    query = {"is_online": True, "status": "approved"}
    if vehicle_type:
        query["vehicle_type"] = vehicle_type

    conductors = await SocioConductorModel.find(query, {"_id": 0, "kyc": 0}).to_list(
        50
    )
    return conductors


# ==================== SOCIO REPARTIDOR ENDPOINTS ====================


async def register_socio_repartidor(
    data: SocioRepartidorRegister, user: dict = Depends(get_current_user)
):
    """Registrar como Socio Repartidor (Micromovilidad/Delivery)"""
    if data.vehicle_type not in REPARTIDOR_VEHICLE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de vehículo inválido. Opciones: {REPARTIDOR_VEHICLE_TYPES}",
        )

    existing = await SocioRepartidorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya tienes un perfil de Socio Repartidor"
        )

    requires_license = data.vehicle_type == "moto_delivery"
    if requires_license and not all(
        [data.license_url, data.circulation_card_url, data.plate_number]
    ):
        raise HTTPException(
            status_code=400,
            detail="Las motos de delivery requieren licencia, carnet de circulación y placa",
        )

    repartidor_doc = {
        "socio_id": f"repartidor_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "vehicle_type": data.vehicle_type,
        "status": "pending_kyc",
        "is_online": False,
        "is_available": True,
        "current_location": None,
        "kyc": {
            "cedula_url": data.cedula_url,
            "cedula_number": data.cedula_number,
            "frontal_photo_url": data.frontal_photo_url,
            "license_url": data.license_url if requires_license else None,
            "circulation_card_url": (
                data.circulation_card_url if requires_license else None
            ),
        },
        "vehicle": (
            {
                "plate_number": data.plate_number,
                "brand": data.vehicle_brand,
                "model": data.vehicle_model,
            }
            if requires_license
            else None
        ),
        "route_restrictions": {
            "avoid_highways": data.vehicle_type in ["bicicleta", "monopatín_electrico"],
            "max_distance_km": (
                5
                if data.vehicle_type == "bicicleta"
                else 10 if data.vehicle_type == "monopatín_electrico" else 20
            ),
        },
        "total_deliveries": 0,
        "total_earnings": 0.0,
        "avg_rating": 5.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await SocioRepartidorModel.insert_one(repartidor_doc)

    if user.get("role") not in ["admin"]:
        await UserModel.update_one(
            {"user_id": user["user_id"]},
            {
                "$set": {
                    "role": "socio_repartidor",
                    "sub_role": data.vehicle_type,
                    "kyc_status": "pending",
                }
            },
        )

    if "_id" in repartidor_doc:
        del repartidor_doc["_id"]

    return {
        "message": "Registro de Socio Repartidor enviado. Pendiente de validación.",
        "socio": repartidor_doc,
    }


async def get_socio_repartidor_profile(user: dict = Depends(get_current_user)):
    """Obtener perfil de Socio Repartidor"""
    socio = await SocioRepartidorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Repartidor"
        )
    return socio


async def socio_repartidor_go_online(
    lat: float, lng: float, user: dict = Depends(get_current_user)
):
    """
    Conectarse como Socio Repartidor.

    GUARDS DE CONEXIÓN:
    1. El perfil debe estar aprobado (status = 'approved')
    2. El fee de activación debe estar pagado (activation_fee_paid = True)
    3. El saldo disponible debe ser >= $1.00
    """
    socio = await SocioRepartidorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Repartidor"
        )

    # Guard 1: Verificar aprobación
    if socio["status"] != "approved":
        raise HTTPException(status_code=403, detail="Tu perfil aún no ha sido aprobado")

    # Guard 2: Verificar fee de activación pagado
    if not socio.get("activation_fee_paid", False):
        raise HTTPException(
            status_code=403,
            detail=f"Debes pagar el fee de activación (${(await get_activation_fee()):.2f}). Recarga tu billetera con al menos $5.00 y contacta al administrador.",
        )

    # Guard 3: Verificar saldo mínimo
    wallet_user = await UserModel.find_one({"user_id": user["user_id"]}, {"_id": 0})
    available = wallet_user.get("wallet_balance", 0) - wallet_user.get("wallet_held", 0)

    if available < (await get_min_balance_to_connect()):
        raise HTTPException(
            status_code=403,
            detail=f"Saldo insuficiente para conectarte. Requieres al menos ${(await get_min_balance_to_connect()):.2f}. Tu saldo disponible: ${available:.2f}. Por favor recarga tu billetera.",
        )

    # Conectar al radar
    await SocioRepartidorModel.update_one(
        {"socio_id": socio["socio_id"]},
        {
            "$set": {
                "is_online": True,
                "is_available": True,
                "current_location": {
                    "lat": lat,
                    "lng": lng,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            }
        },
    )

    return {
        "message": "Estás en línea y disponible para deliveries",
        "current_balance": available,
    }


async def socio_repartidor_go_offline(user: dict = Depends(get_current_user)):
    """Desconectarse como Socio Repartidor"""
    await SocioRepartidorModel.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"is_online": False, "is_available": False}},
    )
    return {"message": "Estás desconectado"}


async def get_nearby_repartidores(
    lat: float, lng: float, vehicle_type: Optional[str] = None
):
    """Obtener repartidores cercanos disponibles"""
    query = {"is_online": True, "is_available": True, "status": "approved"}
    if vehicle_type:
        query["vehicle_type"] = vehicle_type

    repartidores = await SocioRepartidorModel.find(
        query, {"_id": 0, "kyc": 0}
    ).to_list(50)
    return repartidores


# ==================== SOCIO COMERCIAL ENDPOINTS ====================


async def register_socio_comercial(
    data: ComercialRegister, user: dict = Depends(get_current_user)
):
    """Registrar como Socio Comercial"""
    existing = await SocioComercialModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya tienes un perfil de Socio Comercial"
        )

    comercial_doc = {
        "comercial_id": f"comercial_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "store_name": data.store_name,
        "category": data.category,
        "address": data.address,
        "phone": data.phone,
        "description": data.description,
        "logo_url": data.logo_url,
        "status": "pending_kyc",
        "is_open": False,
        "avg_rating": 5.0,
        "total_orders": 0,
        "total_revenue": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await SocioComercialModel.insert_one(comercial_doc)

    if user.get("role") not in ["admin"]:
        await UserModel.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"role": "socio_comercial", "kyc_status": "pending"}},
        )

    if "_id" in comercial_doc:
        del comercial_doc["_id"]

    return {
        "message": "Registro de Socio Comercial enviado",
        "comercial": comercial_doc,
    }


async def get_socio_comercial_profile(user: dict = Depends(get_current_user)):
    comercial = await SocioComercialModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not comercial:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Comercial"
        )
    return comercial


async def create_product(data: ProductCreate, user: dict = Depends(get_current_user)):
    """Agregar producto al inventario"""
    comercial = await SocioComercialModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not comercial:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Comercial"
        )

    product_doc = {
        "product_id": f"prod_{uuid.uuid4().hex[:12]}",
        "comercial_id": comercial["comercial_id"],
        "name": data.name,
        "description": data.description,
        "price": data.price,
        "category": data.category,
        "image_url": data.image_url,
        "available": data.available,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await ProductModel.insert_one(product_doc)

    if "_id" in product_doc:
        del product_doc["_id"]

    return product_doc


async def get_comercial_products(user: dict = Depends(get_current_user)):
    comercial = await SocioComercialModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not comercial:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Comercial"
        )

    products = await ProductModel.find(
        {"comercial_id": comercial["comercial_id"]}, {"_id": 0}
    ).to_list(500)
    return products


async def update_product(
    product_id: str, data: ProductCreate, user: dict = Depends(get_current_user)
):
    comercial = await SocioComercialModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not comercial:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Comercial"
        )

    result = await ProductModel.update_one(
        {"product_id": product_id, "comercial_id": comercial["comercial_id"]},
        {
            "$set": {
                "name": data.name,
                "description": data.description,
                "price": data.price,
                "category": data.category,
                "image_url": data.image_url,
                "available": data.available,
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    return {"message": "Producto actualizado"}


async def delete_product(product_id: str, user: dict = Depends(get_current_user)):
    comercial = await SocioComercialModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not comercial:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Comercial"
        )

    result = await ProductModel.delete_one(
        {"product_id": product_id, "comercial_id": comercial["comercial_id"]}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    return {"message": "Producto eliminado"}


async def get_comercial_orders(user: dict = Depends(get_current_user)):
    comercial = await SocioComercialModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not comercial:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Comercial"
        )

    orders = (
        await MarketOrderModel.find({"store_id": comercial["comercial_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return orders


async def update_order_status(
    order_id: str, status: str, user: dict = Depends(get_current_user)
):
    comercial = await SocioComercialModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not comercial:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Comercial"
        )

    valid_statuses = ["accepted", "rejected", "preparing", "ready", "delivered"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400, detail=f"Estado inválido. Opciones: {valid_statuses}"
        )

    result = await MarketOrderModel.update_one(
        {"order_id": order_id, "store_id": comercial["comercial_id"]},
        {
            "$set": {
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    return {"message": f"Pedido {status}"}


# ==================== MODO DELIVERY TOGGLE ====================


async def toggle_delivery_mode(active: bool, user: dict = Depends(get_current_user)):
    """
    Activar/desactivar modo Delivery para repartidores.

    Cuando está activo (is_delivery_active = True), el repartidor puede
    recibir pedidos del Market.
    """
    socio = await SocioRepartidorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Repartidor"
        )

    if socio["status"] != "approved":
        raise HTTPException(
            status_code=403,
            detail="Tu perfil debe estar aprobado para activar Delivery",
        )

    if not socio.get("activation_fee_paid", False):
        raise HTTPException(
            status_code=403, detail="Debes pagar el fee de activación primero"
        )

    await SocioRepartidorModel.update_one(
        {"user_id": user["user_id"]}, {"$set": {"is_delivery_active": active}}
    )

    return {
        "message": f"Modo Delivery {'activado' if active else 'desactivado'}",
        "is_delivery_active": active,
    }


async def get_delivery_status(user: dict = Depends(get_current_user)):
    """Obtener estado del modo Delivery"""
    socio = await SocioRepartidorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Repartidor"
        )

    return {
        "is_delivery_active": socio.get("is_delivery_active", False),
        "is_online": socio.get("is_online", False),
        "is_available": socio.get("is_available", True),
    }


# ==================== MODO DELIVERY PARA MOTOS (CONDUCTORES) ====================


async def toggle_conductor_delivery_mode(
    active: bool, user: dict = Depends(get_current_user)
):
    """
    Activar/desactivar modo Delivery para conductores de moto.

    Solo disponible para vehicle_type = 'mototaxi'.
    Cuando está activo, el mototaxista puede recibir pedidos de delivery además de pasajeros.
    """
    socio = await SocioConductorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Conductor"
        )

    # Solo motos pueden activar delivery
    if socio.get("vehicle_type") != "mototaxi":
        raise HTTPException(
            status_code=400,
            detail="El modo Delivery solo está disponible para mototaxis",
        )

    if socio["status"] != "approved":
        raise HTTPException(
            status_code=403,
            detail="Tu perfil debe estar aprobado para activar Delivery",
        )

    if not socio.get("activation_fee_paid", False):
        raise HTTPException(
            status_code=403, detail="Debes pagar el fee de activación primero"
        )

    await SocioConductorModel.update_one(
        {"user_id": user["user_id"]}, {"$set": {"is_delivery_active": active}}
    )

    return {
        "message": f"Modo Delivery {'activado' if active else 'desactivado'}",
        "is_delivery_active": active,
    }


async def get_conductor_delivery_status(user: dict = Depends(get_current_user)):
    """Obtener estado del modo Delivery del conductor"""
    socio = await SocioConductorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(
            status_code=404, detail="No tienes perfil de Socio Conductor"
        )

    return {
        "vehicle_type": socio.get("vehicle_type"),
        "is_delivery_active": socio.get("is_delivery_active", False),
        "can_enable_delivery": socio.get("vehicle_type") == "mototaxi",
    }


async def register_socio(
    payload: dict, user: dict = Depends(get_current_user)
):
    """Registro unificado de Socio Conductor desde el formulario paso a paso de la app."""
    personal = payload.get("personal") or {}
    vehicle = payload.get("vehicle") or {}
    docs = payload.get("documents") or {}

    vtype_map = {
        "taxi": "taxi_linea",
        "taxi_linea": "taxi_linea",
        "carro": "carro_particular",
        "carro_particular": "carro_particular",
        "moto": "mototaxi",
        "mototaxi": "mototaxi",
    }
    vehicle_type = vtype_map.get(
        str(vehicle.get("vehicleType", "taxi")).lower(), "carro_particular"
    )
    year_raw = vehicle.get("vehicleYear") or 2020
    try:
        vehicle_year = int(year_raw)
    except (ValueError, TypeError):
        vehicle_year = 2020

    existing = await SocioConductorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya tienes un perfil de Socio Conductor registrado"
        )

    conductor_doc = {
        "socio_id": f"conductor_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "vehicle_type": vehicle_type,
        "status": "pending_kyc",
        "is_online": False,
        "daily_toll_paid": False,
        "current_location": None,
        "kyc": {
            "cedula_url": docs.get("cedula") or "",
            "cedula_number": personal.get("cedula") or "",
            "license_url": docs.get("licencia") or "",
            "license_category": "3ra",
            "medical_card_url": docs.get("certificado_medico") or "",
            "circulation_card_url": docs.get("carnet_circulacion") or "",
            "rcv_insurance_url": docs.get("rcv") or "",
        },
        "vehicle": {
            "plate_number": vehicle.get("plateNumber") or "",
            "brand": vehicle.get("vehicleBrand") or "",
            "model": vehicle.get("vehicleModel") or "",
            "year": vehicle_year,
            "color": vehicle.get("vehicleColor") or "",
            "photo_url": docs.get("foto_vehiculo") or "",
        },
        "taxi_info": None,
        "total_trips": 0,
        "total_earnings": 0.0,
        "avg_rating": 5.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await SocioConductorModel.insert_one(conductor_doc)
    await UserModel.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"sub_role": "socio_conductor", "kyc_status": "pending_review"}},
    )
    if "_id" in conductor_doc:
        del conductor_doc["_id"]
    return {
        "message": "Registro enviado. Pendiente de verificación KYC.",
        "profile": conductor_doc,
    }

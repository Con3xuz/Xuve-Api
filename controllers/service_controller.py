"""Controlador de service - Validaciones y lógica de negocio."""
from models import *
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import os
import uuid
import math

from models import db
from utils.auth import get_current_user
from utils.financial_config import get_commission_rate
from controllers.validators import ServiceRequest, RatingCreate, ProviderAvailability, MatchResult, ServiceType, Message
from controllers.validators import TransactionType
from controllers.payment_method_controller import has_validated_payment_method


# KYC progresivo: el registro es sin fricción (teléfono + nombre + correo) y el
# usuario puede explorar/simular; el gate llega en su PRIMER viaje real, que
# exige un método de pago con titularidad validada (cláusula 3.2). Se puede
# apagar en entornos de prueba con PAYMENT_METHOD_GATE_ENABLED=false.
PAYMENT_METHOD_GATE_ENABLED = os.environ.get(
    "PAYMENT_METHOD_GATE_ENABLED", "true"
).lower() in ("1", "true", "yes")

def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in km between two points using Haversine formula."""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

async def request_service(
    service_req: ServiceRequest, user: dict = Depends(get_current_user)
):
    """
    Solicitar un servicio de transporte.
    Funciona aunque no haya conductores disponibles - el servicio queda en estado 'pending'.
    """
    # Gate de KYC progresivo (primer viaje): exige un método de pago validado.
    if PAYMENT_METHOD_GATE_ENABLED and not await has_validated_payment_method(
        user["user_id"]
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "PAYMENT_METHOD_REQUIRED",
                "message": (
                    "Para solicitar tu primer viaje debes registrar un método de "
                    "pago validado a tu nombre (Términos y Condiciones, cláusula 3.2)."
                ),
            },
        )

    service_doc = {
        "service_id": f"srv_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "user_name": user.get("name", "Cliente"),
        "user_phone": user.get("phone", ""),
        "driver_id": None,
        "service_type": service_req.service_type,
        "status": "pending",
        "pickup_lat": service_req.pickup_lat,
        "pickup_lng": service_req.pickup_lng,
        "pickup_address": service_req.pickup_address or "Sin dirección",
        "dropoff_lat": service_req.dropoff_lat,
        "dropoff_lng": service_req.dropoff_lng,
        "dropoff_address": service_req.dropoff_address or "Sin dirección",
        "vehicle_preference": service_req.vehicle_preference,
        "payment_method": service_req.payment_method or "efectivo",
        "estimated_fare": service_req.estimated_fare,
        "route_id": service_req.route_id,
        "notes": service_req.notes,
        "fare": 0.0,
        "commission": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await ServiceModel.insert_one(service_doc)
    if "_id" in service_doc:
        del service_doc["_id"]
    return service_doc


async def get_active_services(user: dict = Depends(get_current_user)):
    services = await ServiceModel.find(
        {
            "user_id": user["user_id"],
            "status": {"$in": ["pending", "accepted", "in_progress"]},
        },
        {"_id": 0},
    ).to_list(10)
    return services


async def get_driver_pending_services(user: dict = Depends(get_current_user)):
    """Get pending service requests for drivers"""
    services = (
        await ServiceModel.find({"status": "pending"}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(20)
    )
    return services


async def get_service_history(user: dict = Depends(get_current_user)):
    services = (
        await ServiceModel.find({"user_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )
    return services


async def get_service(service_id: str, user: dict = Depends(get_current_user)):
    """Obtener el detalle de un servicio por su ID."""
    service = await ServiceModel.find_one({"service_id": service_id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    return service


async def accept_service(service_id: str, user: dict = Depends(get_current_user)):
    conductor = await SocioConductorModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    driver = await DriverModel.find_one({"user_id": user["user_id"]}, {"_id": 0})
    active_driver = conductor or driver
    if not active_driver or not active_driver.get("is_online"):
        raise HTTPException(
            status_code=403, detail="Debes estar en línea para aceptar servicios"
        )

    driver_id = active_driver.get("socio_id") or active_driver.get("driver_id") or user["user_id"]
    await ServiceModel.update_one(
        {"service_id": service_id},
        {"$set": {"driver_id": driver_id, "status": "accepted"}},
    )
    return {"message": "Servicio aceptado", "service_id": service_id, "driver_id": driver_id}


async def reject_service(service_id: str, user: dict = Depends(get_current_user)):
    """Rechazar una solicitud de servicio pendiente."""
    service = await ServiceModel.find_one({"service_id": service_id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    rejected_by = list(service.get("rejected_by") or [])
    if user["user_id"] not in rejected_by:
        rejected_by.append(user["user_id"])
    await ServiceModel.update_one(
        {"service_id": service_id},
        {"$set": {"rejected_by": rejected_by}},
    )
    return {"message": "Servicio rechazado", "service_id": service_id}


async def send_sos(
    lat: float = 0.0,
    lng: float = 0.0,
    service_id: str = None,
    user: dict = Depends(get_current_user),
):
    """Registrar y notificar una alerta de emergencia SOS durante un viaje."""
    alert_doc = {
        "notification_id": f"sos_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "type": "sos_emergency",
        "title": "Alerta SOS de Emergencia",
        "message": f"Alerta SOS activada por {user.get('name', user['user_id'])}",
        "data": {"lat": lat, "lng": lng, "service_id": service_id},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await NotificationModel.insert_one(alert_doc)
    if service_id:
        await ServiceModel.update_one(
            {"service_id": service_id},
            {"$set": {"sos_triggered": True, "sos_at": alert_doc["created_at"]}},
        )
    return {"message": "Alerta SOS enviada", "status": "ok", "service_id": service_id}


async def complete_service(
    service_id: str, fare: float, user: dict = Depends(get_current_user)
):
    """
    Marcar un servicio/viaje como COMPLETADO (pagado en efectivo).

    LÓGICA DE COMISIÓN (configurable desde admin):
    1. Obtiene la tasa de comisión de la configuración de la plataforma
    2. Descuenta ese monto del balance del conductor/repartidor
    3. Registra una transacción de tipo COMMISSION_DEDUCTION
    """
    service = await ServiceModel.find_one({"service_id": service_id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    # Obtener tasa de comisión desde la configuración del admin
    commission_rate = await get_commission_rate("transport")
    commission = fare * commission_rate

    # Actualizar servicio como completado
    await ServiceModel.update_one(
        {"service_id": service_id},
        {
            "$set": {
                "status": "completed",
                "fare": fare,
                "commission": commission,
                "commission_rate": commission_rate,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Buscar al conductor/repartidor que realizó el servicio
    driver_user_id = None
    driver_type = None

    # Primero buscar en socios_conductores
    if service.get("driver_id"):
        driver = await SocioConductorModel.find_one(
            {"socio_id": service["driver_id"]}, {"_id": 0}
        )
        if driver:
            driver_user_id = driver["user_id"]
            driver_type = "conductor"
        else:
            # Si no es conductor, buscar en socios_repartidores
            repartidor = await SocioRepartidorModel.find_one(
                {"socio_id": service["driver_id"]}, {"_id": 0}
            )
            if repartidor:
                driver_user_id = repartidor["user_id"]
                driver_type = "repartidor"

    # Si no hay driver_id en el servicio, usar el usuario actual si es socio
    if not driver_user_id and user.get("role") in [
        "socio_conductor",
        "socio_repartidor",
    ]:
        driver_user_id = user["user_id"]
        driver_type = (
            "conductor" if user.get("role") == "socio_conductor" else "repartidor"
        )

    # Descontar comisión de la billetera del conductor/repartidor
    if driver_user_id:
        await UserModel.update_one(
            {"user_id": driver_user_id}, {"$inc": {"wallet_balance": -commission}}
        )

        # Registrar transacción de comisión
        await TransactionModel.insert_one(
            {
                "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
                "user_id": driver_user_id,
                "amount_usd": -commission,
                "type": TransactionType.COMMISSION_DEDUCTION.value,
                "status": "completed",
                "reference": service_id,
                "description": f"Comisión {int(commission_rate*100)}% - Viaje #{service_id[-6:]} - Tarifa ${fare:.2f}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Actualizar estadísticas del socio
        if driver_type == "conductor":
            await SocioConductorModel.update_one(
                {"user_id": driver_user_id},
                {"$inc": {"total_trips": 1, "total_earnings": fare - commission}},
            )
        elif driver_type == "repartidor":
            await SocioRepartidorModel.update_one(
                {"user_id": driver_user_id},
                {"$inc": {"total_deliveries": 1, "total_earnings": fare - commission}},
            )

        # Obtener saldo actualizado
        updated_wallet = await UserModel.find_one(
            {"user_id": driver_user_id}, {"_id": 0}
        )
        new_balance = updated_wallet.get("wallet_balance", 0) if updated_wallet else 0

        return {
            "message": "Servicio completado",
            "fare": fare,
            "commission": commission,
            "commission_rate": f"{int(commission_rate*100)}%",
            "net_earnings": fare - commission,
            "new_wallet_balance": new_balance,
        }

    return {
        "message": "Servicio completado (sin conductor asignado)",
        "fare": fare,
        "commission": commission,
    }


# ==================== RATING ENDPOINTS ====================


async def rate_service(
    service_id: str, rating_data: RatingCreate, user: dict = Depends(get_current_user)
):
    """Rate a completed service (user rates driver or driver rates user)"""
    service = await ServiceModel.find_one({"service_id": service_id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    if service["status"] != "completed":
        raise HTTPException(
            status_code=400, detail="Solo puedes calificar servicios completados"
        )

    is_user = service["user_id"] == user["user_id"]
    is_driver_user = service.get("driver_id") is not None

    if not is_user and not is_driver_user:
        raise HTTPException(
            status_code=403, detail="No tienes permiso para calificar este servicio"
        )

    if rating_data.rating < 1 or rating_data.rating > 5:
        raise HTTPException(
            status_code=400, detail="La calificación debe ser entre 1 y 5"
        )

    existing_rating = await RatingModel.find_one(
        {"service_id": service_id, "rater_id": user["user_id"]}, {"_id": 0}
    )

    if existing_rating:
        raise HTTPException(status_code=400, detail="Ya calificaste este servicio")

    if is_user:
        driver = await DriverModel.find_one(
            {"driver_id": service["driver_id"]}, {"_id": 0}
        )
        rated_id = driver["user_id"] if driver else None
        rating_type = "user_to_driver"
    else:
        rated_id = service["user_id"]
        rating_type = "driver_to_user"

    rating_doc = {
        "rating_id": f"rat_{uuid.uuid4().hex[:12]}",
        "service_id": service_id,
        "rater_id": user["user_id"],
        "rated_id": rated_id,
        "rating_type": rating_type,
        "rating": rating_data.rating,
        "comment": rating_data.comment,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await RatingModel.insert_one(rating_doc)

    rating_field = "user_rating" if is_user else "driver_rating"
    await ServiceModel.update_one(
        {"service_id": service_id}, {"$set": {rating_field: rating_data.rating}}
    )

    if rated_id:
        all_ratings = await RatingModel.find({"rated_id": rated_id}, {"_id": 0}).to_list(
            1000
        )
        if all_ratings:
            avg_rating = sum(r["rating"] for r in all_ratings) / len(all_ratings)
            await UserModel.update_one(
                {"user_id": rated_id}, {"$set": {"avg_rating": round(avg_rating, 2)}}
            )

    if "_id" in rating_doc:
        del rating_doc["_id"]

    return {"message": "Calificación enviada", "rating": rating_doc}


async def get_service_ratings(service_id: str, user: dict = Depends(get_current_user)):
    """Get ratings for a specific service"""
    ratings = await RatingModel.find({"service_id": service_id}, {"_id": 0}).to_list(10)
    user_has_rated = any(r["rater_id"] == user["user_id"] for r in ratings)
    return {"ratings": ratings, "user_has_rated": user_has_rated}


# Rating by user_id


async def get_user_ratings(user_id: str):
    """Get all ratings for a user"""
    ratings = (
        await RatingModel.find({"rated_id": user_id}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )

    if ratings:
        avg = sum(r["rating"] for r in ratings) / len(ratings)
        stats = {
            "average_rating": round(avg, 2),
            "total_ratings": len(ratings),
            "rating_distribution": {
                "5": len([r for r in ratings if r["rating"] == 5]),
                "4": len([r for r in ratings if r["rating"] == 4]),
                "3": len([r for r in ratings if r["rating"] == 3]),
                "2": len([r for r in ratings if r["rating"] == 2]),
                "1": len([r for r in ratings if r["rating"] == 1]),
            },
        }
    else:
        stats = {"average_rating": 0, "total_ratings": 0, "rating_distribution": {}}

    return {"ratings": ratings, "stats": stats}


# ==================== MATCHING ENDPOINTS ====================

async def update_provider_availability(
    availability: ProviderAvailability, user: dict = Depends(get_current_user)
):
    """Update provider location and availability for matching"""
    # Check if user is a provider
    if user.get("role") not in ["socio_conductor", "socio_repartidor"]:
        raise HTTPException(status_code=403, detail="Solo proveedores pueden actualizar disponibilidad")
    
    availability_doc = {
        "provider_id": user["user_id"],
        "location": {
            "latitude": availability.location.latitude,
            "longitude": availability.location.longitude,
            "address": availability.location.address
        },
        "service_types": [st.value for st in availability.service_types],
        "is_available": availability.is_available,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    
    await ProviderAvailabilityModel.update_one(
        {"provider_id": user["user_id"]},
        {"$set": availability_doc},
        upsert=True
    )
    return {"message": "Disponibilidad actualizada"}

async def find_matches(service_id: str, user: dict = Depends(get_current_user)):
    """Find available providers near the service location"""
    service = await ServiceModel.find_one({"service_id": service_id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    if service["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="No tienes acceso a este servicio")
    
    if not service.get("pickup_lat") or not service.get("pickup_lng"):
        raise HTTPException(status_code=400, detail="Ubicación de recogida requerida")
    
    # Find available providers within 10km
    pickup_lat = service["pickup_lat"]
    pickup_lng = service["pickup_lng"]
    max_distance_km = 10
    
    providers = await ProviderAvailabilityModel.find(
        {"is_available": True}, {"_id": 0}
    ).to_list(50)
    
    matches = []
    for provider in providers:
        prov_lat = provider["location"]["latitude"]
        prov_lng = provider["location"]["longitude"]
        distance = calculate_distance(pickup_lat, pickup_lng, prov_lat, prov_lng)
        
        if distance <= max_distance_km:
            # Check if provider supports service type
            service_type = ServiceType(service["service_type"])
            if service_type.value in provider["service_types"]:
                estimated_time = int(distance * 3)  # Rough estimate: 3 min per km
                matches.append(MatchResult(
                    service_id=service_id,
                    provider_id=provider["provider_id"],
                    distance_km=round(distance, 2),
                    estimated_time_min=estimated_time
                ))
    
    # Sort by distance
    matches.sort(key=lambda x: x.distance_km)
    return {"matches": matches[:10]}  # Top 10 closest


# ==================== CHAT ENDPOINTS ====================

async def send_message(
    service_id: str,
    content: str = Body(...),
    user: dict = Depends(get_current_user),
):
    """Send a message in a service chat"""
    service = await ServiceModel.find_one({"service_id": service_id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    # Check if user is part of the service
    if service["user_id"] != user["user_id"] and service.get("driver_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="No tienes acceso a este chat")
    
    message_doc = {
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "service_id": service_id,
        "sender_id": user["user_id"],
        "sender_name": user.get("name", "Usuario"),
        "content": content.strip(),
        "message_type": "text",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await ServiceMessageModel.insert_one(message_doc)
    if "_id" in message_doc:
        del message_doc["_id"]
    
    return message_doc

async def get_messages(service_id: str, user: dict = Depends(get_current_user)):
    """Get messages for a service chat"""
    service = await ServiceModel.find_one({"service_id": service_id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    # Check if user is part of the service
    if service["user_id"] != user["user_id"] and service.get("driver_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="No tienes acceso a este chat")
    
    messages = await ServiceMessageModel.find(
        {"service_id": service_id}, 
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)  # Last 100 messages
    
    return {"messages": messages}

"""Controlador de rent - Validaciones y lógica de negocio."""
from models import *
from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
import uuid

from models import db
from utils.auth import get_current_user
from controllers.validators import RentVehicleCreate



# ==================== PUBLIC RENT ENDPOINTS ====================


async def get_available_cars():
    """Lista de carros disponibles para alquilar"""
    cars = await RentCarModel.find(
        {"status": {"$in": ["available", "approved"]}, "available": True}, {"_id": 0}
    ).to_list(100)
    return cars


async def get_available_cars_alias():
    """Alias de /cars para compatibilidad con frontend"""
    cars = await RentCarModel.find(
        {"status": {"$in": ["available", "approved"]}, "available": True}, {"_id": 0}
    ).to_list(100)
    return cars


async def get_car_details(car_id: str):
    """Detalles de un carro específico"""
    car = await RentCarModel.find_one({"vehicle_id": car_id}, {"_id": 0})
    if not car:
        # Try with car_id field for legacy data
        car = await RentCarModel.find_one({"car_id": car_id}, {"_id": 0})
    if not car:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return car


async def request_rent(
    car_id: str, start_date: str, end_date: str, user: dict = Depends(get_current_user)
):
    """Solicitar alquiler de un vehículo"""
    car = await RentCarModel.find_one({"vehicle_id": car_id}, {"_id": 0})
    if not car:
        car = await RentCarModel.find_one({"car_id": car_id}, {"_id": 0})
    if not car:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    request_doc = {
        "request_id": f"rent_req_{uuid.uuid4().hex[:12]}",
        "vehicle_id": car_id,
        "renter_id": user["user_id"],
        "owner_id": car.get("owner_id"),
        "start_date": start_date,
        "end_date": end_date,
        "daily_rate": car.get("daily_rate", car.get("daily_price", 0)),
        "deposit_amount": car.get("deposit_amount", 0),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await RentRequestModel.insert_one(request_doc)

    if "_id" in request_doc:
        del request_doc["_id"]

    return {"message": "Solicitud de alquiler enviada", "request": request_doc}


# ==================== USER ENDPOINTS (Frontend compatibility) ====================


async def get_my_cars(user: dict = Depends(get_current_user)):
    """Obtener mis autos publicados para alquiler"""
    vehicles = await RentCarModel.find(
        {"owner_id": user["user_id"]}, {"_id": 0}
    ).to_list(50)
    return vehicles


async def get_my_rentals(user: dict = Depends(get_current_user)):
    """Obtener mis alquileres activos (como cliente)"""
    # Get user's rent requests
    requests = (
        await RentRequestModel.find({"renter_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )

    # Enrich with car details
    rentals = []
    for req in requests:
        car = await RentCarModel.find_one(
            {
                "$or": [
                    {"vehicle_id": req.get("vehicle_id")},
                    {"car_id": req.get("vehicle_id")},
                ]
            },
            {"_id": 0},
        )
        rental = {
            "rental_id": req.get("request_id"),
            "car_brand": car.get("brand") if car else "N/A",
            "car_model": car.get("model") if car else "N/A",
            "plate_number": car.get("plate_number") if car else "N/A",
            "owner_id": car.get("owner_id") if car else None,
            "owner_name": car.get("owner_name") if car else "N/A",
            "owner_phone": car.get("owner_phone") if car else None,
            "deposit_amount": req.get("deposit_amount", 0),
            "status": req.get("status", "pending"),
            "created_at": req.get("created_at"),
        }
        rentals.append(rental)

    return rentals


async def create_rent_request(request: Request, user: dict = Depends(get_current_user)):
    """Solicitar alquiler de un vehículo (usado por frontend)"""
    body = await request.json()
    car_id = body.get("car_id")
    hold_id = body.get("hold_id")  # Optional hold ID for deposit

    car = await RentCarModel.find_one(
        {"$or": [{"vehicle_id": car_id}, {"car_id": car_id}]}, {"_id": 0}
    )
    if not car:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    request_doc = {
        "request_id": f"rent_req_{uuid.uuid4().hex[:12]}",
        "vehicle_id": car_id,
        "renter_id": user["user_id"],
        "owner_id": car.get("owner_id"),
        "daily_rate": car.get("daily_rate", car.get("daily_price", 0)),
        "deposit_amount": car.get("deposit_amount", 0),
        "hold_id": hold_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await RentRequestModel.insert_one(request_doc)

    if "_id" in request_doc:
        del request_doc["_id"]

    return {"message": "Solicitud de alquiler enviada", "request": request_doc}


async def publish_car(request: Request, user: dict = Depends(get_current_user)):
    """Publicar auto para alquiler (frontend uses this)"""
    body = await request.json()

    vehicle_doc = {
        "vehicle_id": f"rent_{uuid.uuid4().hex[:12]}",
        "car_id": f"rent_{uuid.uuid4().hex[:12]}",
        "owner_id": user["user_id"],
        "owner_name": user.get("name", "Usuario"),
        "owner_phone": user.get("phone", ""),
        "brand": body.get("brand"),
        "model": body.get("model"),
        "year": body.get("year"),
        "color": body.get("color"),
        "plate_number": body.get("plateNumber"),
        "condition": body.get("condition", "bueno"),
        "daily_price": float(body.get("dailyPrice", 0)),
        "daily_rate": float(body.get("dailyPrice", 0)),
        "deposit_amount": float(body.get("dailyPrice", 0)) * 2,  # 2 days as deposit
        "location": body.get("location"),
        "description": body.get("description"),
        "photos": body.get("photos", []),
        "image_url": body.get("photos", [""])[0] if body.get("photos") else "",
        "available": True,
        "status": "available",
        "rating": 5.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await RentCarModel.insert_one(vehicle_doc)

    if "_id" in vehicle_doc:
        del vehicle_doc["_id"]

    return vehicle_doc


# ==================== RENT OWNER ENDPOINTS ====================


async def get_owner_vehicles(user: dict = Depends(get_current_user)):
    """Obtener vehículos del propietario"""
    vehicles = await RentCarModel.find(
        {"owner_id": user["user_id"]}, {"_id": 0}
    ).to_list(50)
    return vehicles


async def create_rent_vehicle(
    data: RentVehicleCreate, user: dict = Depends(get_current_user)
):
    """Publicar vehículo para alquiler"""
    vehicle_doc = {
        "vehicle_id": f"rent_{uuid.uuid4().hex[:12]}",
        "owner_id": user["user_id"],
        "brand": data.brand,
        "model": data.model,
        "year": data.year,
        "color": data.color,
        "plate_number": data.plate_number,
        "daily_rate": data.daily_rate,
        "deposit_amount": data.deposit_amount,
        "location": data.location,
        "description": data.description,
        "image_url": data.image_url,
        "available": True,
        "blocked_dates": [],
        "status": "pending_docs",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await RentCarModel.insert_one(vehicle_doc)

    if user.get("role") not in ["admin", "rent_owner"]:
        await UserModel.update_one(
            {"user_id": user["user_id"]}, {"$set": {"role": "rent_owner"}}
        )

    if "_id" in vehicle_doc:
        del vehicle_doc["_id"]

    return vehicle_doc


async def update_rent_vehicle(
    vehicle_id: str, updates: dict, user: dict = Depends(get_current_user)
):
    """Actualizar vehículo (disponibilidad, fechas bloqueadas, etc.)"""
    vehicle = await RentCarModel.find_one(
        {"vehicle_id": vehicle_id, "owner_id": user["user_id"]}, {"_id": 0}
    )
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    allowed_fields = [
        "available",
        "blocked_dates",
        "daily_rate",
        "deposit_amount",
        "location",
        "description",
        "image_url",
    ]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}

    if update_data:
        await RentCarModel.update_one({"vehicle_id": vehicle_id}, {"$set": update_data})

    return {"message": "Vehículo actualizado"}


async def get_rent_requests(user: dict = Depends(get_current_user)):
    """Obtener solicitudes de alquiler para los vehículos del propietario"""
    vehicles = await RentCarModel.find(
        {"owner_id": user["user_id"]}, {"_id": 0}
    ).to_list(50)
    vehicle_ids = [v["vehicle_id"] for v in vehicles]

    requests = (
        await RentRequestModel.find({"vehicle_id": {"$in": vehicle_ids}}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )

    return requests


async def accept_rent_request(request_id: str, user: dict = Depends(get_current_user)):
    """Aceptar solicitud de alquiler (congela depósito del cliente)"""
    request = await RentRequestModel.find_one({"request_id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    vehicle = await RentCarModel.find_one(
        {"vehicle_id": request["vehicle_id"], "owner_id": user["user_id"]}, {"_id": 0}
    )
    if not vehicle:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    if request["status"] != "pending":
        raise HTTPException(status_code=400, detail="Esta solicitud ya fue procesada")

    if vehicle.get("deposit_amount", 0) > 0:
        renter = await UserModel.find_one({"user_id": request["renter_id"]}, {"_id": 0})
        available = renter.get("wallet_balance", 0) - renter.get("wallet_held", 0)

        if available < vehicle["deposit_amount"]:
            raise HTTPException(
                status_code=400,
                detail="El cliente no tiene fondos suficientes para el depósito",
            )

        hold_doc = {
            "hold_id": f"hold_{uuid.uuid4().hex[:12]}",
            "user_id": request["renter_id"],
            "amount_usd": vehicle["deposit_amount"],
            "reason": "rent_deposit",
            "reference_id": request_id,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await WalletHoldModel.insert_one(hold_doc)

        await UserModel.update_one(
            {"user_id": request["renter_id"]},
            {"$inc": {"wallet_held": vehicle["deposit_amount"]}},
        )

    await RentRequestModel.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "status": "accepted",
                "accepted_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": "Solicitud aceptada. Depósito congelado."}


async def reject_rent_request(request_id: str, user: dict = Depends(get_current_user)):
    """Rechazar solicitud de alquiler"""
    request = await RentRequestModel.find_one({"request_id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    vehicle = await RentCarModel.find_one(
        {"vehicle_id": request["vehicle_id"], "owner_id": user["user_id"]}, {"_id": 0}
    )
    if not vehicle:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    await RentRequestModel.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "status": "rejected",
                "rejected_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": "Solicitud rechazada"}

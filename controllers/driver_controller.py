"""Controlador de driver - Validaciones y lógica de negocio."""
from models import *
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import uuid

from models import db
from utils.auth import get_current_user
from utils.financial_config import get_toll_amount
from controllers.validators import DriverRegister



async def register_driver(
    driver_data: DriverRegister, user: dict = Depends(get_current_user)
):
    existing = await DriverModel.find_one({"user_id": driver_data.user_id}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Ya tienes un perfil de conductor")

    if not driver_data.is_owner:
        if not all(
            [
                driver_data.cedula_url,
                driver_data.license_url,
                driver_data.medical_card_url,
                driver_data.owner_cedula,
                driver_data.owner_name,
                driver_data.owner_phone,
            ]
        ):
            raise HTTPException(
                status_code=400,
                detail="Los conductores 'Avance' requieren documentación adicional del dueño",
            )

    driver_doc = {
        "driver_id": f"driver_{uuid.uuid4().hex[:12]}",
        "user_id": driver_data.user_id,
        "vehicle_type": driver_data.vehicle_type,
        "is_owner": driver_data.is_owner,
        "status": "pending",
        "is_online": False,
        "daily_toll_paid": False,
        "cedula_url": driver_data.cedula_url,
        "license_url": driver_data.license_url,
        "medical_card_url": driver_data.medical_card_url,
        "owner_cedula": driver_data.owner_cedula,
        "owner_name": driver_data.owner_name,
        "owner_phone": driver_data.owner_phone,
        "plate_number": driver_data.plate_number,
        "vehicle_brand": driver_data.vehicle_brand,
        "vehicle_model": driver_data.vehicle_model,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await DriverModel.insert_one(driver_doc)

    current_user = await UserModel.find_one({"user_id": driver_data.user_id}, {"_id": 0})
    if current_user and current_user.get("role") != "admin":
        await UserModel.update_one(
            {"user_id": driver_data.user_id}, {"$set": {"role": "driver"}}
        )

    if "_id" in driver_doc:
        del driver_doc["_id"]

    return {
        "message": "Registro enviado. Pendiente de validación en sede Mérida.",
        "driver": driver_doc,
    }


async def get_driver_profile(user: dict = Depends(get_current_user)):
    driver = await DriverModel.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not driver:
        raise HTTPException(status_code=404, detail="No eres conductor registrado")
    return driver


async def driver_go_online(user: dict = Depends(get_current_user)):
    driver = await DriverModel.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not driver:
        raise HTTPException(status_code=404, detail="No eres conductor registrado")

    if driver["status"] != "approved":
        raise HTTPException(status_code=403, detail="Tu perfil aún no ha sido aprobado")

    # Obtener peaje desde la configuración del admin
    toll_amount = await get_toll_amount(driver["vehicle_type"])
    wallet_user = await UserModel.find_one({"user_id": user["user_id"]}, {"_id": 0})

    if not driver.get("daily_toll_paid"):
        if wallet_user.get("wallet_balance", 0) < toll_amount:
            raise HTTPException(
                status_code=400,
                detail=f"Saldo insuficiente para peaje diario (${toll_amount})",
            )

        await UserModel.update_one(
            {"user_id": user["user_id"]}, {"$inc": {"wallet_balance": -toll_amount}}
        )

        await TransactionModel.insert_one(
            {
                "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
                "user_id": user["user_id"],
                "amount_usd": -toll_amount,
                "type": "toll",
                "status": "completed",
                "description": f"Peaje diario - {driver['vehicle_type']}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        await DriverModel.update_one(
            {"driver_id": driver["driver_id"]}, {"$set": {"daily_toll_paid": True}}
        )

    await DriverModel.update_one(
        {"driver_id": driver["driver_id"]}, {"$set": {"is_online": True}}
    )

    return {"message": "Estás en línea", "toll_paid": toll_amount}


async def driver_go_offline(user: dict = Depends(get_current_user)):
    driver = await DriverModel.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not driver:
        raise HTTPException(status_code=404, detail="No eres conductor registrado")

    await DriverModel.update_one(
        {"driver_id": driver["driver_id"]}, {"$set": {"is_online": False}}
    )

    return {"message": "Estás desconectado"}


async def approve_driver(driver_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    await DriverModel.update_one(
        {"driver_id": driver_id}, {"$set": {"status": "approved"}}
    )
    return {"message": "Conductor aprobado"}

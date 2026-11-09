"""Controlador de user - Validaciones y lógica de negocio."""
from models import *
from fastapi import APIRouter, Depends

from models import db
from utils.auth import get_current_user
from controllers.validators import VALID_ROLES



async def get_user_dashboard_route(user: dict = Depends(get_current_user)):
    """Devuelve la ruta del dashboard según el rol del usuario"""
    role = user.get("role", "user")
    sub_role = user.get("sub_role")

    routes = {
        "user": "/dashboard/cliente",
        "socio_conductor": "/dashboard/conductor",
        "socio_repartidor": "/dashboard/repartidor",
        "socio_comercial": "/dashboard/comercial",
        "rent_owner": "/dashboard/rent",
        "carga_pesada": "/dashboard/carga",
        "line_admin": "/dashboard/linea",
        "chofer_linea": "/dashboard/chofer",
        "admin": "/admin",
    }

    return {
        "role": role,
        "sub_role": sub_role,
        "dashboard_route": routes.get(role, "/dashboard/cliente"),
        "kyc_status": user.get("kyc_status", "pending"),
        "available_balance": user.get("wallet_balance", 0) - user.get("wallet_held", 0),
    }


# Profile endpoint
async def get_user_profile(user: dict = Depends(get_current_user)):
    """Obtener perfil completo del usuario actual"""
    # Get additional profile data based on role
    profile_data = {
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "name": user.get("name"),
        "phone": user.get("phone"),
        "picture": user.get("picture"),
        "role": user.get("role"),
        "sub_role": user.get("sub_role"),
        "wallet_balance": user.get("wallet_balance", 0),
        "wallet_held": user.get("wallet_held", 0),
        "available_balance": user.get("wallet_balance", 0) - user.get("wallet_held", 0),
        "status": user.get("status"),
        "kyc_status": user.get("kyc_status"),
        "avg_rating": user.get("avg_rating", 5.0),
        "created_at": user.get("created_at"),
    }

    # Add role-specific data
    role = user.get("role")
    if role == "socio_conductor":
        socio = await SocioConductorModel.find_one(
            {"user_id": user["user_id"]}, {"_id": 0}
        )
        if socio:
            profile_data["socio_profile"] = socio
    elif role == "socio_repartidor":
        socio = await SocioRepartidorModel.find_one(
            {"user_id": user["user_id"]}, {"_id": 0}
        )
        if socio:
            profile_data["socio_profile"] = socio
    elif role == "socio_comercial":
        socio = await SocioComercialModel.find_one(
            {"user_id": user["user_id"]}, {"_id": 0}
        )
        if socio:
            profile_data["socio_profile"] = socio
    elif role == "line_admin":
        linea = await LineaTransporteModel.find_one(
            {"admin_user_id": user["user_id"]}, {"_id": 0}
        )
        if linea:
            profile_data["linea_profile"] = linea

    return profile_data

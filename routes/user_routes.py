from fastapi import APIRouter, Depends

from utils.database import db
from utils.auth import get_current_user
from models.user_models import VALID_ROLES

router = APIRouter(prefix="/user", tags=["User"])


@router.get("/dashboard-route")
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
@router.get("/profile")
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
        socio = await db.socios_conductores.find_one(
            {"user_id": user["user_id"]}, {"_id": 0}
        )
        if socio:
            profile_data["socio_profile"] = socio
    elif role == "socio_repartidor":
        socio = await db.socios_repartidores.find_one(
            {"user_id": user["user_id"]}, {"_id": 0}
        )
        if socio:
            profile_data["socio_profile"] = socio
    elif role == "socio_comercial":
        socio = await db.socios_comerciales.find_one(
            {"user_id": user["user_id"]}, {"_id": 0}
        )
        if socio:
            profile_data["socio_profile"] = socio
    elif role == "line_admin":
        linea = await db.lineas_transporte.find_one(
            {"admin_user_id": user["user_id"]}, {"_id": 0}
        )
        if linea:
            profile_data["linea_profile"] = linea

    return profile_data

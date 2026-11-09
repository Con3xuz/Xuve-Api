"""Controlador de routes - Validaciones y lógica de negocio."""
from models import *
from fastapi import APIRouter, HTTPException, Depends

from models import db
from utils.auth import get_current_user



async def get_fixed_routes():
    routes = await FixedRouteModel.find({"is_active": True}, {"_id": 0}).to_list(100)
    return routes


async def get_route(route_id: str):
    route = await FixedRouteModel.find_one({"route_id": route_id}, {"_id": 0})
    if not route:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    return route


async def create_route(route: dict, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    await FixedRouteModel.insert_one(route)
    if "_id" in route:
        del route["_id"]
    return route

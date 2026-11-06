from fastapi import APIRouter, HTTPException, Depends

from utils.database import db
from utils.auth import get_current_user

router = APIRouter(prefix="/routes", tags=["Fixed Routes"])


@router.get("")
async def get_fixed_routes():
    routes = await db.fixed_routes.find({"is_active": True}, {"_id": 0}).to_list(100)
    return routes


@router.get("/{route_id}")
async def get_route(route_id: str):
    route = await db.fixed_routes.find_one({"route_id": route_id}, {"_id": 0})
    if not route:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    return route


@router.post("")
async def create_route(route: dict, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    await db.fixed_routes.insert_one(route)
    if "_id" in route:
        del route["_id"]
    return route

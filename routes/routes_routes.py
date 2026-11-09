"""Rutas HTTP de routes - Conecta cada endpoint directamente con controllers.routes_controller."""
from fastapi import APIRouter
from controllers import routes_controller

router = APIRouter(prefix="/routes", tags=["Fixed Routes"])

router.get("")(routes_controller.get_fixed_routes)
router.get("/{route_id}")(routes_controller.get_route)
router.post("")(routes_controller.create_route)

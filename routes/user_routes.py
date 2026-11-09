"""Rutas HTTP de user - Conecta cada endpoint directamente con controllers.user_controller."""
from fastapi import APIRouter
from controllers import user_controller

router = APIRouter(prefix="/user", tags=["User"])

router.get("/dashboard-route")(user_controller.get_user_dashboard_route)
router.get("/profile")(user_controller.get_user_profile)

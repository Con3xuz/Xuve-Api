"""Rutas HTTP de seed - Conecta cada endpoint directamente con controllers.seed_controller."""
from fastapi import APIRouter
from controllers import seed_controller

router = APIRouter(tags=["Seed"])

router.api_route("/seed", methods=["GET", "POST"])(seed_controller.seed_database)

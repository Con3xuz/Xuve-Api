"""Rutas HTTP de driver - Conecta cada endpoint directamente con controllers.driver_controller."""
from fastapi import APIRouter
from controllers import driver_controller

router = APIRouter(prefix="/driver", tags=["Driver (Legacy)"])

router.post("/register")(driver_controller.register_driver)
router.get("/profile")(driver_controller.get_driver_profile)
router.post("/go-online")(driver_controller.driver_go_online)
router.post("/go-offline")(driver_controller.driver_go_offline)
router.post("/approve/{driver_id}")(driver_controller.approve_driver)

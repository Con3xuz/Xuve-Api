"""Rutas HTTP de subscription - Conecta cada endpoint directamente con controllers.subscription_controller."""
from fastapi import APIRouter
from controllers import subscription_controller

router = APIRouter(prefix="/subscription", tags=["Subscription"])

router.get("/status")(subscription_controller.get_my_subscription_status)
router.post("/activate")(subscription_controller.activate_my_subscription)
router.post("/deactivate")(subscription_controller.deactivate_my_subscription)
router.get("/info")(subscription_controller.get_subscription_info)
router.get("/admin/stats")(subscription_controller.get_admin_subscription_stats)

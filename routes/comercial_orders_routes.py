"""Rutas HTTP de comercial_orders - Conecta cada endpoint directamente con controllers.comercial_orders_controller."""
from fastapi import APIRouter
from controllers import comercial_orders_controller

router = APIRouter(prefix="/comercial/orders", tags=["Comercial Orders"])

router.get("/incoming")(comercial_orders_controller.get_incoming_orders)
router.get("/active")(comercial_orders_controller.get_active_orders)
router.get("/history")(comercial_orders_controller.get_order_history)
router.post("/{order_id}/accept")(comercial_orders_controller.accept_order)
router.post("/{order_id}/reject")(comercial_orders_controller.reject_order)
router.post("/{order_id}/ready")(comercial_orders_controller.mark_order_ready)
router.get("/stats/today")(comercial_orders_controller.get_today_stats)

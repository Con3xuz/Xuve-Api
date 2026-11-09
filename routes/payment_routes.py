"""Rutas HTTP de payment - Conecta cada endpoint directamente con controllers.payment_controller."""
from fastapi import APIRouter
from controllers import payment_controller

router = APIRouter(prefix="/payments", tags=["Payments"])

router.post("/subscribe")(payment_controller.subscribe)
router.post("/webhook")(payment_controller.payments_webhook)
router.post("/simulate/{reference}")(payment_controller.simulate_payment)
router.get("/subscription-status")(payment_controller.subscription_status)

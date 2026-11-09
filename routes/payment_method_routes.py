"""Rutas HTTP de payment_method - Conecta cada endpoint directamente con controllers.payment_method_controller."""
from fastapi import APIRouter
from controllers import payment_method_controller

router = APIRouter(prefix="/user/payment-methods", tags=["Payment Methods"])

router.post("/pre-validate")(payment_method_controller.pre_validate)
router.post("")(payment_method_controller.register_payment_method)
router.get("")(payment_method_controller.list_payment_methods)

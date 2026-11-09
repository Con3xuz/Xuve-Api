"""Rutas HTTP de market - Conecta cada endpoint directamente con controllers.market_controller."""
from fastapi import APIRouter
from controllers import market_controller

router = APIRouter(prefix="/market", tags=["Market"])

router.get("/stores")(market_controller.get_market_stores)
router.get("/stores/{store_id}")(market_controller.get_store)
router.get("/stores/{store_id}/products")(market_controller.get_store_products)
router.get("/products")(market_controller.get_all_products)
router.post("/orders")(market_controller.create_order)
router.post("/orders/{order_id}/confirm")(market_controller.confirm_order)
router.post("/orders/{order_id}/complete")(market_controller.complete_order)
router.get("/orders")(market_controller.get_user_orders)
router.get("/orders/{order_id}")(market_controller.get_order)
router.get("/delivery/pending")(market_controller.get_pending_deliveries)
router.get("/orders/delivery/pending")(market_controller.get_pending_deliveries)
router.post("/delivery/{order_id}/accept")(market_controller.accept_delivery)
router.post("/orders/{order_id}/accept-delivery")(market_controller.accept_delivery)

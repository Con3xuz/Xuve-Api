"""Rutas HTTP de rent - Conecta cada endpoint directamente con controllers.rent_controller."""
from fastapi import APIRouter
from controllers import rent_controller

router = APIRouter(prefix="/rent", tags=["Rent a Car"])

router.get("/cars")(rent_controller.get_available_cars)
router.get("/available")(rent_controller.get_available_cars_alias)
router.get("/cars/{car_id}")(rent_controller.get_car_details)
router.post("/cars/{car_id}/request")(rent_controller.request_rent)
router.get("/my-cars")(rent_controller.get_my_cars)
router.get("/my-rentals")(rent_controller.get_my_rentals)
router.post("/request")(rent_controller.create_rent_request)
router.post("/publish")(rent_controller.publish_car)
router.get("/owner/vehicles")(rent_controller.get_owner_vehicles)
router.post("/owner/vehicles")(rent_controller.create_rent_vehicle)
router.patch("/owner/vehicles/{vehicle_id}")(rent_controller.update_rent_vehicle)
router.get("/owner/requests")(rent_controller.get_rent_requests)
router.post("/owner/requests/{request_id}/accept")(rent_controller.accept_rent_request)
router.post("/owner/requests/{request_id}/reject")(rent_controller.reject_rent_request)

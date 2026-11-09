"""Rutas HTTP de service - Conecta cada endpoint directamente con controllers.service_controller."""
from fastapi import APIRouter
from controllers import service_controller

router = APIRouter(prefix="/services", tags=["Services"])
ratings_router = APIRouter(prefix="/ratings", tags=["Ratings"])
sos_router = APIRouter(tags=["SOS"])

sos_router.post("/sos")(service_controller.send_sos)
router.post("/sos")(service_controller.send_sos)
router.post("/request")(service_controller.request_service)
router.get("/active")(service_controller.get_active_services)
router.get("/driver/pending")(service_controller.get_driver_pending_services)
router.get("/history")(service_controller.get_service_history)
router.get("/{service_id}")(service_controller.get_service)
router.post("/{service_id}/accept")(service_controller.accept_service)
router.post("/{service_id}/reject")(service_controller.reject_service)
router.post("/{service_id}/complete")(service_controller.complete_service)
router.post("/{service_id}/rate")(service_controller.rate_service)
router.get("/{service_id}/rating")(service_controller.get_service_ratings)
ratings_router.get("/user/{user_id}")(service_controller.get_user_ratings)
router.post("/provider/availability")(service_controller.update_provider_availability)
router.get("/{service_id}/match")(service_controller.find_matches)
router.post("/{service_id}/messages")(service_controller.send_message)
router.get("/{service_id}/messages")(service_controller.get_messages)

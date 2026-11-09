"""Rutas HTTP de geo - Conecta cada endpoint directamente con controllers.geo_controller."""
from fastapi import APIRouter
from controllers import geo_controller

router = APIRouter(prefix="/geo", tags=["Geo"])

router.get("/autocomplete")(geo_controller.autocomplete)
router.get("/place/{place_id}")(geo_controller.place_details)
router.get("/geocode")(geo_controller.geocode)
router.get("/directions")(geo_controller.directions)
router.get("/estimate-fare")(geo_controller.estimate_fare_endpoint)
router.get("/quote")(geo_controller.quote)
router.get("/distance-matrix")(geo_controller.distance_matrix)

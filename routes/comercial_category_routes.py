"""Rutas HTTP de comercial_category - Conecta cada endpoint directamente con controllers.comercial_category_controller."""
from fastapi import APIRouter
from controllers import comercial_category_controller

router = APIRouter(prefix="/comercial", tags=["Comercial Categories"])

router.get("/categories")(comercial_category_controller.get_all_categories)
router.post("/profile/setup")(comercial_category_controller.setup_store_profile)
router.post("/register")(comercial_category_controller.setup_store_profile)
router.get("/profile")(comercial_category_controller.get_store_profile)
router.patch("/profile/toggle-open")(comercial_category_controller.toggle_store_open)
router.get("/stores/by-category/{category}")(comercial_category_controller.get_stores_by_category)
router.get("/stores/all")(comercial_category_controller.get_all_stores)

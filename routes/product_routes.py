"""Rutas HTTP de product - Conecta cada endpoint directamente con controllers.product_controller."""
from fastapi import APIRouter
from controllers import product_controller

router = APIRouter(prefix="/store/products", tags=["Store Products"])

router.get("")(product_controller.get_my_products)
router.get("/stats")(product_controller.get_products_stats)
router.post("")(product_controller.create_product)
router.get("/{product_id}")(product_controller.get_product)
router.put("/{product_id}")(product_controller.update_product)
router.delete("/{product_id}")(product_controller.delete_product)
router.post("/{product_id}/images")(product_controller.add_product_image)
router.delete("/{product_id}/images/{image_id}")(product_controller.remove_product_image)
router.put("/{product_id}/images/{image_id}/primary")(product_controller.set_primary_image)
router.get("/import/template")(product_controller.get_import_template)
router.post("/import/csv")(product_controller.import_products_csv)
router.post("/import/preview")(product_controller.preview_import)
router.get("/categories/list")(product_controller.get_categories)
router.get("/categories/my-store")(product_controller.get_my_store_categories)
router.post("/bulk/update-availability")(product_controller.bulk_update_availability)
router.post("/bulk/delete")(product_controller.bulk_delete_products)
router.post("/bulk/update-stock")(product_controller.bulk_update_stock)

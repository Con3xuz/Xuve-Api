"""Rutas HTTP de upload - Conecta cada endpoint directamente con controllers.upload_controller."""
from fastapi import APIRouter
from controllers import upload_controller

router = APIRouter(prefix="/upload", tags=["Upload"])
uploads_router = APIRouter(tags=["Uploads Static"])

router.post("/image")(upload_controller.upload_image)
uploads_router.get("/uploads/{filename}")(upload_controller.get_uploaded_file)

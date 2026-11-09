"""Rutas HTTP de auth - Conecta cada endpoint directamente con controllers.auth_controller."""
from fastapi import APIRouter
from controllers import auth_controller

router = APIRouter(prefix="/auth", tags=["Authentication"])

router.post("/register")(auth_controller.register)
router.post("/verify-email")(auth_controller.verify_email)
router.post("/resend-verification")(auth_controller.resend_verification)
router.post("/forgot-password")(auth_controller.forgot_password)
router.post("/reset-password")(auth_controller.reset_password)
router.post("/login")(auth_controller.login)
router.post("/google/session")(auth_controller.google_session)
router.get("/me")(auth_controller.get_me)
router.post("/logout")(auth_controller.logout)
router.patch("/profile")(auth_controller.update_profile)

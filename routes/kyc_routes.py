"""Rutas HTTP de kyc - Conecta cada endpoint directamente con controllers.kyc_controller."""
from fastapi import APIRouter
from controllers import kyc_controller

router = APIRouter(prefix="/kyc", tags=["KYC"])

router.post("/submit")(kyc_controller.submit_kyc_request)
router.get("/my-status")(kyc_controller.get_my_kyc_status)
router.get("/roles-info")(kyc_controller.get_roles_info)
router.post("/verify/driver")(kyc_controller.verify_driver_dossier)
router.post("/verify/merchant")(kyc_controller.verify_merchant_dossier)
router.post("/admin/approve/{kyc_id}")(kyc_controller.admin_approve_kyc)
router.post("/admin/reject/{kyc_id}")(kyc_controller.admin_reject_kyc)
router.post("/webhook")(kyc_controller.kyc_webhook)
router.post("/simulate/{kyc_id}")(kyc_controller.simulate_kyc_decision)

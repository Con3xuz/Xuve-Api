"""Rutas HTTP de admin - Conecta cada endpoint directamente con controllers.admin_controller."""
from fastapi import APIRouter
from controllers import admin_controller

router = APIRouter(prefix="/admin", tags=["Admin"])

router.get("/stats")(admin_controller.get_admin_stats)
router.get("/drivers")(admin_controller.get_drivers_list)
router.get("/transactions")(admin_controller.get_transactions_list)
router.get("/kyc-requests")(admin_controller.get_kyc_requests)
router.get("/kyc-requests/{kyc_id}")(admin_controller.get_kyc_request_detail)
router.post("/kyc-requests/{kyc_id}/approve")(admin_controller.approve_kyc_request)
router.post("/kyc-requests/{kyc_id}/reject")(admin_controller.reject_kyc_request)
router.get("/kyc/all-pending")(admin_controller.get_all_pending_kyc)
router.post("/kyc/{type}/{entity_id}/approve")(admin_controller.approve_entity_kyc)
router.post("/kyc/{type}/{entity_id}/reject")(admin_controller.reject_entity_kyc)
router.get("/verticales/urbanas")(admin_controller.get_lineas_urbanas)
router.get("/verticales/rent-a-car")(admin_controller.get_rent_stats)
router.get("/verticales/carga")(admin_controller.get_carga_stats)
router.get("/verticales/terminales")(admin_controller.get_terminales_stats)
router.get("/config/financial")(admin_controller.get_financial_config)
router.post("/config/financial")(admin_controller.update_financial_config)
router.post("/kyc/conductor/{socio_id}/approve")(admin_controller.approve_conductor_kyc)
router.post("/kyc/repartidor/{socio_id}/approve")(admin_controller.approve_repartidor_kyc)
router.post("/kyc/comercial/{socio_id}/approve")(admin_controller.approve_comercial_kyc)
router.get("/kyc/pending")(admin_controller.get_pending_kyc)
router.get("/financial/stats")(admin_controller.get_financial_stats)

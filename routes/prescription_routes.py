"""Rutas HTTP de prescription - Conecta cada endpoint directamente con controllers.prescription_controller."""
from fastapi import APIRouter
from controllers import prescription_controller

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])

router.post("")(prescription_controller.create_prescription)
router.get("/my-prescriptions")(prescription_controller.get_doctor_prescriptions)
router.get("/stats")(prescription_controller.get_doctor_stats)
router.get("/patient/my-prescriptions")(prescription_controller.get_patient_prescriptions)
router.get("/pharmacy/incoming")(prescription_controller.get_pharmacy_prescriptions)
router.put("/{prescription_id}/status")(prescription_controller.update_prescription_status)
router.get("/{prescription_id}")(prescription_controller.get_prescription)

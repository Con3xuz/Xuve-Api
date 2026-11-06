"""
OMNI - Rutas de Recetas Médicas
================================
Endpoints para gestión de recetas digitales.
Flujo: Médico crea receta → Se envía a Farmabien → Paciente aprueba y paga → Delivery
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone
from utils.auth import get_current_user
from utils.database import db
from models.prescription_models import PrescriptionCreate, PrescriptionUpdate
import uuid

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])


def generate_prescription_id():
    return f"rx_{uuid.uuid4().hex[:12]}"


# ==================== MÉDICO: Crear y gestionar recetas ====================


@router.post("")
async def create_prescription(
    data: PrescriptionCreate, user: dict = Depends(get_current_user)
):
    """Médico crea una receta digital"""
    if user.get("role") != "medico":
        raise HTTPException(
            status_code=403, detail="Solo los médicos pueden crear recetas"
        )

    medico = await db.medicos.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not medico or medico.get("status") != "approved":
        raise HTTPException(
            status_code=403, detail="Tu perfil médico no está aprobado aún"
        )

    now = datetime.now(timezone.utc).isoformat()

    # Buscar paciente por cédula
    patient = await db.users.find_one(
        {"$or": [{"cedula": data.patient_cedula}, {"phone": data.patient_phone}]},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1, "phone": 1},
    )

    # Buscar farmacia destino
    pharmacy = None
    if data.pharmacy_store_id:
        pharmacy = await db.store_profiles.find_one(
            {"store_id": data.pharmacy_store_id},
            {"_id": 0, "store_id": 1, "store_name": 1},
        )

    # Si no se especificó farmacia, buscar Farmabien por defecto
    if not pharmacy:
        pharmacy = await db.store_profiles.find_one(
            {"category": "farmacia"}, {"_id": 0, "store_id": 1, "store_name": 1}
        )

    prescription = {
        "prescription_id": generate_prescription_id(),
        "doctor_id": user["user_id"],
        "doctor_name": user.get("name", ""),
        "doctor_specialty": medico.get("specialty", ""),
        "doctor_license": medico.get("license_number", ""),
        "patient_name": data.patient_name,
        "patient_cedula": data.patient_cedula,
        "patient_phone": data.patient_phone,
        "patient_email": data.patient_email,
        "patient_user_id": patient["user_id"] if patient else None,
        "diagnosis": data.diagnosis,
        "medications": [m.dict() for m in data.medications],
        "notes": data.notes,
        "pharmacy_store_id": pharmacy["store_id"] if pharmacy else None,
        "pharmacy_name": pharmacy["store_name"] if pharmacy else None,
        "status": "created",
        "pharmacy_notes": "",
        "created_at": now,
        "updated_at": now,
    }

    await db.prescriptions.insert_one(prescription)
    prescription.pop("_id", None)

    # Crear notificación para la farmacia
    if pharmacy:
        await db.notifications.insert_one(
            {
                "notification_id": f"notif_{uuid.uuid4().hex[:8]}",
                "user_id": None,
                "store_id": pharmacy["store_id"],
                "type": "new_prescription",
                "title": "Nueva Receta Médica",
                "message": f"{user.get('name', '')} envió una receta para {data.patient_name}",
                "reference_id": prescription["prescription_id"],
                "read": False,
                "created_at": now,
            }
        )

    # Crear notificación para el paciente si existe
    if patient:
        await db.notifications.insert_one(
            {
                "notification_id": f"notif_{uuid.uuid4().hex[:8]}",
                "user_id": patient["user_id"],
                "type": "prescription_received",
                "title": "Nueva Receta Médica",
                "message": f"{user.get('name', '')} te envió una receta médica",
                "reference_id": prescription["prescription_id"],
                "read": False,
                "created_at": now,
            }
        )

    return {"message": "Receta creada y enviada", "prescription": prescription}


@router.get("/my-prescriptions")
async def get_doctor_prescriptions(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Médico obtiene sus recetas emitidas"""
    if user.get("role") != "medico":
        raise HTTPException(status_code=403, detail="Solo médicos")

    query = {"doctor_id": user["user_id"]}
    if status:
        query["status"] = status

    total = await db.prescriptions.count_documents(query)
    skip = (page - 1) * limit
    prescriptions = (
        await db.prescriptions.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )

    return {
        "prescriptions": prescriptions,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        },
    }


@router.get("/stats")
async def get_doctor_stats(user: dict = Depends(get_current_user)):
    """Estadísticas del médico"""
    if user.get("role") != "medico":
        raise HTTPException(status_code=403, detail="Solo médicos")

    total = await db.prescriptions.count_documents({"doctor_id": user["user_id"]})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_count = await db.prescriptions.count_documents(
        {"doctor_id": user["user_id"], "created_at": {"$regex": f"^{today}"}}
    )
    pending = await db.prescriptions.count_documents(
        {"doctor_id": user["user_id"], "status": "created"}
    )
    dispensed = await db.prescriptions.count_documents(
        {"doctor_id": user["user_id"], "status": "dispensed"}
    )

    return {
        "total_prescriptions": total,
        "today": today_count,
        "pending": pending,
        "dispensed": dispensed,
    }


# ==================== PACIENTE: Ver sus recetas ====================


@router.get("/patient/my-prescriptions")
async def get_patient_prescriptions(user: dict = Depends(get_current_user)):
    """Paciente ve sus recetas recibidas"""
    prescriptions = (
        await db.prescriptions.find({"patient_user_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )

    return {"prescriptions": prescriptions}


# ==================== FARMACIA: Gestionar recetas recibidas ====================


@router.get("/pharmacy/incoming")
async def get_pharmacy_prescriptions(
    status: Optional[str] = None, user: dict = Depends(get_current_user)
):
    """Farmacia obtiene recetas recibidas"""
    store = await db.store_profiles.find_one(
        {"user_id": user["user_id"]}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    query = {"pharmacy_store_id": store["store_id"]}
    if status:
        query["status"] = status

    prescriptions = (
        await db.prescriptions.find(query, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return {"prescriptions": prescriptions}


@router.put("/{prescription_id}/status")
async def update_prescription_status(
    prescription_id: str,
    data: PrescriptionUpdate,
    user: dict = Depends(get_current_user),
):
    """Actualizar estado de receta (farmacia o médico)"""
    prescription = await db.prescriptions.find_one(
        {"prescription_id": prescription_id}, {"_id": 0}
    )
    if not prescription:
        raise HTTPException(status_code=404, detail="Receta no encontrada")

    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if data.status:
        update["status"] = data.status
    if data.pharmacy_notes:
        update["pharmacy_notes"] = data.pharmacy_notes

    await db.prescriptions.update_one(
        {"prescription_id": prescription_id}, {"$set": update}
    )

    return {"message": "Receta actualizada"}


@router.get("/{prescription_id}")
async def get_prescription(
    prescription_id: str, user: dict = Depends(get_current_user)
):
    """Obtener detalle de una receta"""
    prescription = await db.prescriptions.find_one(
        {"prescription_id": prescription_id}, {"_id": 0}
    )
    if not prescription:
        raise HTTPException(status_code=404, detail="Receta no encontrada")

    # Verificar que el usuario tiene acceso
    has_access = (
        user["user_id"] == prescription.get("doctor_id")
        or user["user_id"] == prescription.get("patient_user_id")
        or user.get("role") == "admin"
    )

    # O es la farmacia destino
    if not has_access:
        store = await db.store_profiles.find_one(
            {"user_id": user["user_id"]}, {"_id": 0, "store_id": 1}
        )
        if store and store["store_id"] == prescription.get("pharmacy_store_id"):
            has_access = True

    if not has_access:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta receta")

    return prescription

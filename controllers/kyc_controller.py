"""Controlador de kyc - Validaciones y lógica de negocio."""
from models import *
"""
KYC Routes - Endpoints para solicitudes de verificación
"""

from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from datetime import datetime, timezone
import uuid
import json

from models import db
from utils.auth import get_current_user
from utils.kyc_provider import (
    start_verification,
    verify_webhook_signature,
    is_mock_mode as kyc_is_mock_mode,
    verify_role_dossier,
    KYCServiceError,
)
from controllers.validators import KYC_ELEVATABLE_ROLES


# Roles cuyo expediente se verifica como DRIVER o MERCHANT en xuve-kyc-service.
# Los roles de persona al volante van por /verify/driver; los de negocio /
# representante legal van por /verify/merchant.
DRIVER_DOSSIER_ROLES = {
    "socio_conductor",
    "socio_repartidor",
    "carga_pesada",
    "chofer_linea",
    "chofer_urbano",
    "transporte_interurbano",
}
MERCHANT_DOSSIER_ROLES = {
    "socio_comercial",
    "rent_owner",
    "line_admin",
    "urban_line_admin",
}


def _entity_type_for_role(role: str | None) -> str:
    if role in DRIVER_DOSSIER_ROLES:
        return "DRIVER"
    if role in MERCHANT_DOSSIER_ROLES:
        return "MERCHANT"
    return "CUSTOMER"


async def _apply_kyc_decision(kyc_id: str, decision: str, reason: str = "") -> dict:
    """Aplica una decisión de KYC (approved/rejected) a la solicitud y al usuario.
    Compartido por el webhook del proveedor y por la aprobación/rechazo manual."""
    kyc = await KYCRequestModel.find_one({"kyc_id": kyc_id}, {"_id": 0})
    if not kyc:
        raise HTTPException(status_code=404, detail="Solicitud KYC no encontrada")
    if kyc.get("status") in ("approved", "rejected"):
        return {"message": "Solicitud ya procesada", "kyc_id": kyc_id, "status": kyc["status"]}

    now = datetime.now(timezone.utc).isoformat()
    user_id = kyc.get("user_id")

    if decision == "approved":
        await KYCRequestModel.update_one(
            {"kyc_id": kyc_id}, {"$set": {"status": "approved", "reviewed_at": now}}
        )
        new_role = kyc.get("requested_role")
        # Defensa en profundidad: nunca elevar a un rol fuera de la whitelist
        # (p.ej. "admin"). Si el rol solicitado no es válido, se aprueba el KYC
        # pero NO se cambia el rol del usuario.
        role_update = {"kyc_status": "approved"}
        if new_role in KYC_ELEVATABLE_ROLES:
            role_update["role"] = new_role

        # Snapshot inmutable de identidad verificada: lo consume el motor de
        # titularidad de métodos de pago (cláusula 3.2). Sin cédula en el
        # expediente no hay snapshot y el usuario no podrá registrar métodos
        # de pago hasta verificar su identidad.
        personal = kyc.get("personal_data") or {}
        id_number = personal.get("cedula_number")
        full_name = kyc.get("user_name")
        if id_number and full_name:
            role_update["verified_identity"] = {
                "kyc_request_id": f"req_{uuid.uuid4().hex[:16]}",
                "entity_type": _entity_type_for_role(new_role),
                "id_number": id_number,
                "full_name": full_name,
            }
        await UserModel.update_one(
            {"user_id": user_id},
            {"$set": role_update, "$unset": {"pending_role": ""}},
        )
        return {"message": "KYC aprobado", "kyc_id": kyc_id, "user_id": user_id,
                "new_role": new_role, "status": "approved"}

    await KYCRequestModel.update_one(
        {"kyc_id": kyc_id},
        {"$set": {"status": "rejected", "reviewed_at": now, "rejection_reason": reason}},
    )
    await UserModel.update_one(
        {"user_id": user_id},
        {"$set": {"kyc_status": "rejected"}, "$unset": {"pending_role": ""}},
    )
    return {"message": "KYC rechazado", "kyc_id": kyc_id, "user_id": user_id, "status": "rejected"}


async def submit_kyc_request(request: Request, user: dict = Depends(get_current_user)):
    """
    Enviar una nueva solicitud KYC.
    El wizard del frontend envía los datos según el rol solicitado.
    """
    body = await request.json()

    user_id = user.get("user_id")

    # SEGURIDAD: el rol solicitado debe estar en la whitelist (nunca admin/user).
    requested_role = body.get("requested_role")
    if requested_role not in KYC_ELEVATABLE_ROLES:
        raise HTTPException(status_code=400, detail="Rol solicitado no válido")

    # Verificar si ya tiene una solicitud pendiente
    existing = await KYCRequestModel.find_one(
        {"user_id": user_id, "status": {"$in": ["pending", "in_review"]}}
    )

    if existing:
        raise HTTPException(
            status_code=400, detail="Ya tienes una solicitud KYC pendiente de revisión"
        )

    # Crear solicitud
    kyc_id = f"kyc_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    kyc_request = {
        "kyc_id": kyc_id,
        "user_id": user_id,
        "user_email": user.get("email"),
        "user_name": user.get("name"),
        "user_phone": user.get("phone"),
        "requested_role": body.get("requested_role"),
        "sub_role": body.get("sub_role"),
        "status": "pending",
        # Sub-esquemas opcionales
        "personal_data": body.get("personal_data"),
        "driver_license": body.get("driver_license"),
        "medical_data": body.get("medical_data"),
        "medical_license_data": body.get("medical_license_data"),
        "vehicle_light": body.get("vehicle_light"),
        "vehicle_heavy": body.get("vehicle_heavy"),
        "company_data": body.get("company_data"),
        "store_data": body.get("store_data"),
        "rent_owner_data": body.get("rent_owner_data"),
        "submitted_at": now,
        "created_at": now,
    }

    await KYCRequestModel.insert_one(kyc_request)

    # Inicia la verificación con el proveedor externo (o mock) y pasa a in_review.
    verification = await start_verification(kyc_id, user)
    await KYCRequestModel.update_one(
        {"kyc_id": kyc_id},
        {"$set": {
            "status": "in_review",
            "provider": verification["provider"],
            "provider_ref": verification["provider_ref"],
        }},
    )
    await UserModel.update_one(
        {"user_id": user_id},
        {"$set": {"pending_role": body.get("requested_role"), "kyc_status": "in_review"}},
    )

    return {
        "message": "Solicitud KYC enviada; verificación en curso.",
        "kyc_id": kyc_id,
        "status": "in_review",
        "provider_ref": verification["provider_ref"],
        "mock": verification.get("mock", False),
    }


async def get_my_kyc_status(user: dict = Depends(get_current_user)):
    """Obtener el estado de KYC del usuario actual"""
    user_id = user.get("user_id")

    # Buscar solicitud más reciente
    kyc = await KYCRequestModel.find_one(
        {"user_id": user_id}, {"_id": 0}, sort=[("created_at", -1)]
    )

    if not kyc:
        return {
            "has_kyc": False,
            "kyc_status": user.get("kyc_status", "none"),
            "current_role": user.get("role"),
            "pending_role": user.get("pending_role"),
        }

    return {
        "has_kyc": True,
        "kyc_id": kyc.get("kyc_id"),
        "kyc_status": kyc.get("status"),
        "requested_role": kyc.get("requested_role"),
        "submitted_at": kyc.get("submitted_at"),
        "reviewed_at": kyc.get("reviewed_at"),
        "rejection_reason": kyc.get("rejection_reason"),
        "current_role": user.get("role"),
        "pending_role": user.get("pending_role"),
    }


async def get_roles_info():
    """Obtener información sobre los roles disponibles para KYC"""
    return {
        "roles": [
            {
                "id": "user",
                "label": "Cliente",
                "description": "Verificación de identidad",
                "requirements": ["Foto frontal de cédula", "Selfie de verificación"],
            },
            {
                "id": "socio_conductor",
                "label": "Conductor",
                "description": "Taxi o carro particular",
                "requirements": [
                    "Licencia 2da/3ra",
                    "RCV",
                    "Carnet de Circulación",
                    "Fotos del vehículo",
                ],
            },
            {
                "id": "socio_repartidor",
                "label": "Repartidor",
                "description": "Moto delivery o bicicleta",
                "requirements": ["Licencia 2da/3ra", "RCV", "Fotos del vehículo"],
            },
            {
                "id": "carga_pesada",
                "label": "Carga Pesada",
                "description": "Camiones, cisternas, mudanzas",
                "requirements": [
                    "Licencia 5ta",
                    "Certificado Médico Vial",
                    "RCV Pesado",
                    "Capacidad del vehículo",
                ],
            },
            {
                "id": "chofer_linea",
                "label": "Chofer Interurbano",
                "description": "Chofer de terminal/línea",
                "requirements": [
                    "Licencia 5ta",
                    "Certificado Médico Vial",
                    "RCV Pesado",
                ],
            },
            {
                "id": "medico",
                "label": "Médico",
                "description": "Profesional de la salud",
                "requirements": ["Cédula MPPS", "Título Universitario", "Especialidad"],
            },
            {
                "id": "line_admin",
                "label": "Terminal Admin",
                "description": "Administrador de terminal B2B",
                "requirements": [
                    "RIF Jurídico",
                    "Registro Mercantil",
                    "Permiso de Ruta",
                ],
            },
            {
                "id": "socio_comercial",
                "label": "Comercial",
                "description": "Tienda, restaurante, farmacia",
                "requirements": ["RIF", "Fotos del Local"],
            },
            {
                "id": "rent_owner",
                "label": "Rent Owner",
                "description": "Propietario de vehículo para alquiler",
                "requirements": [
                    "Título de Propiedad",
                    "RCV",
                    "Fotos detalladas del vehículo",
                ],
            },
        ]
    }


# ═════════════════════════════════════════════════════════════════════════════
# Elevación de rol vía xuve-kyc-service: el expediente COMPLETO (documentos +
# prueba de vida) viaja al microservicio, que decide en línea (sin webhook).
# ═════════════════════════════════════════════════════════════════════════════


async def _read_dossier_file(field: str, upload: UploadFile) -> tuple[str, bytes, str]:
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"Archivo vacío: {field}")
    return (upload.filename or field, content, upload.content_type or "application/octet-stream")


async def _process_role_dossier(
    user: dict, requested_role: str, entity: str, files: dict[str, tuple[str, bytes, str]]
) -> dict:
    """Envía el expediente al microservicio y aplica el veredicto en línea.

    APPROVED       -> rol elevado + kyc_status approved + snapshot de identidad.
    MANUAL_REVIEW  -> kyc_status in_review (decide un admin con /admin/approve).
    REJECTED       -> kyc_status rejected.
    """
    user_id = user["user_id"]

    existing = await KYCRequestModel.find_one(
        {"user_id": user_id, "status": {"$in": ["pending", "in_review"]}}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya tienes una solicitud KYC pendiente de revisión"
        )

    try:
        verification = await verify_role_dossier(entity, user_id, files)
    except KYCServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    kyc_id = f"kyc_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    verdict = verification.get("status")
    extracted = verification.get("extracted_data") or {}

    # El snapshot de identidad exige cédula + nombre extraídos del documento.
    # Un APPROVED sin esos datos se degrada a revisión manual (fail-closed).
    has_identity = bool(extracted.get("id_number") and extracted.get("full_name"))
    if verdict == "APPROVED" and not has_identity:
        verdict = "MANUAL_REVIEW"

    status_map = {"APPROVED": "approved", "MANUAL_REVIEW": "in_review", "REJECTED": "rejected"}
    kyc_status = status_map.get(verdict, "in_review")

    await KYCRequestModel.insert_one(
        {
            "kyc_id": kyc_id,
            "user_id": user_id,
            "user_email": user.get("email"),
            "user_name": user.get("name"),
            "user_phone": user.get("phone"),
            "requested_role": requested_role,
            "status": kyc_status,
            "provider": "xuve-kyc-service",
            "provider_ref": verification.get("request_id"),
            "entity_type": verification.get("entity_type"),
            "biometric_score": verification.get("biometric_score"),
            "liveness_passed": verification.get("liveness_passed"),
            "forensic_risk": verification.get("forensic_risk"),
            "extracted_data": extracted,
            "flags": verification.get("flags", []),
            "submitted_at": now,
            "created_at": now,
            **({"reviewed_at": now} if kyc_status in ("approved", "rejected") else {}),
        }
    )

    if kyc_status == "approved":
        role_update = {"kyc_status": "approved"}
        if requested_role in KYC_ELEVATABLE_ROLES:
            role_update["role"] = requested_role
        role_update["verified_identity"] = {
            "kyc_request_id": verification["request_id"],
            "entity_type": verification.get("entity_type", _entity_type_for_role(requested_role)),
            "id_number": extracted["id_number"],
            "full_name": extracted["full_name"],
            **({"rif": extracted["merchant_rif"]} if extracted.get("merchant_rif") else {}),
            **({"company_name": extracted["company_name"]} if extracted.get("company_name") else {}),
        }
        await UserModel.update_one(
            {"user_id": user_id}, {"$set": role_update, "$unset": {"pending_role": ""}}
        )
    elif kyc_status == "in_review":
        await UserModel.update_one(
            {"user_id": user_id},
            {"$set": {"kyc_status": "in_review", "pending_role": requested_role}},
        )
    else:
        await UserModel.update_one(
            {"user_id": user_id},
            {"$set": {"kyc_status": "rejected"}, "$unset": {"pending_role": ""}},
        )

    return {
        "kyc_id": kyc_id,
        "status": kyc_status,
        "requested_role": requested_role,
        "provider_ref": verification.get("request_id"),
        "biometric_score": verification.get("biometric_score"),
        "forensic_risk": verification.get("forensic_risk"),
        "flags": verification.get("flags", []),
    }


async def verify_driver_dossier(
    requested_role: str = Form("socio_conductor"),
    document_front: UploadFile = File(..., description="Cédula/Pasaporte (frontal)"),
    liveness_video: UploadFile = File(..., description="Video de prueba de vida (~3s)"),
    driver_license: UploadFile = File(..., description="Licencia de conducir"),
    vehicle_card: UploadFile = File(..., description="Carnet de circulación"),
    vehicle_photo: UploadFile = File(..., description="Foto del vehículo con placa"),
    user: dict = Depends(get_current_user),
):
    """Expediente completo de conductor (elevación de rol DRIVER)."""
    if requested_role not in (KYC_ELEVATABLE_ROLES & DRIVER_DOSSIER_ROLES):
        raise HTTPException(status_code=400, detail="Rol solicitado no válido para expediente de conductor")
    files = {
        "document_front": await _read_dossier_file("document_front", document_front),
        "liveness_video": await _read_dossier_file("liveness_video", liveness_video),
        "driver_license": await _read_dossier_file("driver_license", driver_license),
        "vehicle_card": await _read_dossier_file("vehicle_card", vehicle_card),
        "vehicle_photo": await _read_dossier_file("vehicle_photo", vehicle_photo),
    }
    return await _process_role_dossier(user, requested_role, "driver", files)


async def verify_merchant_dossier(
    requested_role: str = Form("socio_comercial"),
    document_front: UploadFile = File(..., description="Cédula del representante legal"),
    liveness_video: UploadFile = File(..., description="Video de prueba de vida (~3s)"),
    rif_document: UploadFile = File(..., description="RIF comercial o firma personal"),
    storefront_photo: UploadFile = File(..., description="Fachada del local comercial"),
    user: dict = Depends(get_current_user),
):
    """Expediente completo de comercio (elevación de rol MERCHANT)."""
    if requested_role not in (KYC_ELEVATABLE_ROLES & MERCHANT_DOSSIER_ROLES):
        raise HTTPException(status_code=400, detail="Rol solicitado no válido para expediente de comercio")
    files = {
        "document_front": await _read_dossier_file("document_front", document_front),
        "liveness_video": await _read_dossier_file("liveness_video", liveness_video),
        "rif_document": await _read_dossier_file("rif_document", rif_document),
        "storefront_photo": await _read_dossier_file("storefront_photo", storefront_photo),
    }
    return await _process_role_dossier(user, requested_role, "merchant", files)


async def admin_approve_kyc(kyc_id: str, user: dict = Depends(get_current_user)):
    """Aprobar solicitud KYC manualmente (solo admin)."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    return await _apply_kyc_decision(kyc_id, "approved")


async def admin_reject_kyc(kyc_id: str, reason: str = "", user: dict = Depends(get_current_user)):
    """Rechazar solicitud KYC manualmente (solo admin)."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    return await _apply_kyc_decision(kyc_id, "rejected", reason)


async def kyc_webhook(request: Request):
    """
    Webhook del proveedor externo de KYC. Verifica firma HMAC y aplica la
    decisión automáticamente (approved/rejected). Lo llama el proveedor (sin
    sesión, con firma). `reference` = kyc_id que enviamos al iniciar la sesión.
    """
    raw = await request.body()
    signature = request.headers.get("X-Signature", "")
    if not verify_webhook_signature(raw, signature):
        raise HTTPException(status_code=401, detail="Firma de webhook inválida")

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload inválido")

    kyc_id = payload.get("reference") or payload.get("kyc_id")
    provider_status = (payload.get("status") or "").lower()
    if not kyc_id:
        raise HTTPException(status_code=400, detail="reference (kyc_id) requerido")

    if provider_status in ("approved", "verified", "completed", "success"):
        return await _apply_kyc_decision(kyc_id, "approved")
    if provider_status in ("rejected", "declined", "failed"):
        return await _apply_kyc_decision(kyc_id, "rejected", payload.get("reason", ""))

    # Estado intermedio (processing/pending): se registra, no decide.
    await KYCRequestModel.update_one(
        {"kyc_id": kyc_id}, {"$set": {"provider_status": provider_status}}
    )
    return {"message": "Estado intermedio registrado", "kyc_id": kyc_id,
            "provider_status": provider_status}


async def simulate_kyc_decision(
    kyc_id: str,
    decision: str = "approved",
    reason: str = "",
    user: dict = Depends(get_current_user),
):
    """SOLO MOCK: simula la decisión del proveedor para probar el flujo local
    sin llamadas a internet. Deshabilitado cuando hay proveedor real activo."""
    if not kyc_is_mock_mode():
        raise HTTPException(status_code=403, detail="Simulación deshabilitada (proveedor real activo)")
    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision debe ser approved|rejected")
    return await _apply_kyc_decision(kyc_id, decision, reason)

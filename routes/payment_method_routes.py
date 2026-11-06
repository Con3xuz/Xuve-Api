"""
Métodos de pago del usuario — KYC progresivo (T&C cláusulas 3.2 y 6).
=====================================================================
Montado bajo /api/v1 => endpoints públicos:

  POST /api/v1/user/payment-methods/pre-validate  -> proxy de pre-validación en vivo
  POST /api/v1/user/payment-methods               -> validación definitiva + guardado
  GET  /api/v1/user/payment-methods               -> instrumentos del usuario (enmascarados)

Mapeo de veredictos del motor de titularidad (xuve-kyc-service):
  MATCH           -> instrumento ACTIVE, 201 Created
  MANUAL_REVIEW   -> instrumento PENDING_VALIDATION, 202 Accepted
  MISMATCH        -> 400 Bad Request (cláusula 3.2 + remaining_attempts)
  SUSPEND_ACCOUNT -> cuenta SUSPENDED_PENDING_REVIEW, JWTs revocados, 403 (cláusula 6)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import uuid

from utils.database import db
from utils.auth import get_current_user
from utils.kyc_provider import (
    KYCServiceError,
    pre_validate_payment_method,
    validate_payment_method_ownership,
)
from utils.ratelimit import limiter
from models.payment_method_models import (
    ACCOUNT_SUSPENDED_PENDING_REVIEW,
    PAYMENT_METHOD_ACTIVE,
    PAYMENT_METHOD_PENDING,
    PaymentMethodPayload,
    mask_identifier,
)

router = APIRouter(prefix="/user/payment-methods", tags=["Payment Methods"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def has_validated_payment_method(user_id: str) -> bool:
    """Gate de KYC progresivo: ¿tiene el usuario al menos un instrumento ACTIVE?

    Lo consumen los flujos de primer pago / primer viaje (p.ej. /services/request).
    """
    method = await db.payment_methods.find_one(
        {"user_id": user_id, "status": PAYMENT_METHOD_ACTIVE}, {"_id": 0}
    )
    return method is not None


def _public_view(doc: dict) -> dict:
    """Vista segura del instrumento (sin fingerprint completo ni metadatos internos)."""
    return {
        "payment_method_id": doc.get("payment_method_id"),
        "method_type": doc.get("method_type"),
        "holder_full_name": doc.get("holder_full_name"),
        "masked_identifier": doc.get("masked_identifier"),
        "bank_code": doc.get("bank_code"),
        "status": doc.get("status"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def _masked_identifier(payload: PaymentMethodPayload) -> str | None:
    """Identificador enmascarado según el tipo de instrumento (para la UI)."""
    if payload.method_type == "PAGO_MOVIL":
        return mask_identifier(payload.phone_number)
    if payload.method_type == "BANK_ACCOUNT_VE":
        return mask_identifier(payload.account_number)
    if payload.method_type == "ZELLE":
        # Un email de Zelle se enmascara conservando el dominio.
        ident = payload.zelle_identifier or ""
        if "@" in ident:
            local, _, domain = ident.partition("@")
            return f"{mask_identifier(local, 2)}@{domain}"
        return mask_identifier(ident)
    if payload.method_type == "BINANCE_PAY":
        return mask_identifier(payload.binance_pay_id)
    return None


def _kyc_error_response(exc: KYCServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": "KYC_SERVICE_ERROR", "detail": exc.detail},
    )


@router.post("/pre-validate")
@limiter.limit("60/minute")
async def pre_validate(
    request: Request,
    payload: PaymentMethodPayload,
    user: dict = Depends(get_current_user),
):
    """Proxy de pre-validación sintáctica en tiempo real (mientras el usuario tipea).

    Passthrough del microservicio: 200 con `formatted_data` canónico (la app debe
    enviar exactamente eso al guardar) o 422 con los errores por campo. No toca
    la BD, no genera strikes.
    """
    try:
        status_code, body = await pre_validate_payment_method(
            payload.to_service_payload()
        )
    except KYCServiceError as exc:
        return _kyc_error_response(exc)
    return JSONResponse(status_code=status_code, content=body)


async def _suspend_account(user_id: str, verdict: dict) -> None:
    """Cláusula 6: suspende la cuenta y revoca TODAS las sesiones/JWT.

    - `status: suspended` la corta en `get_current_user` (chequeo de cuenta activa).
    - `token_version++` invalida todos los JWT emitidos.
    - Se borran las sesiones de Google activas.
    """
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "status": "suspended",
                "account_status": ACCOUNT_SUSPENDED_PENDING_REVIEW,
                "suspension_reason": "OWNERSHIP_STRIKES",
                "suspension_tc_clauses": verdict.get("tc_clauses", ["3.2", "6"]),
                "suspended_at": _now(),
            },
            "$inc": {"token_version": 1},
        },
    )
    await db.user_sessions.delete_many({"user_id": user_id})


@router.post("")
@limiter.limit("10/minute")
async def register_payment_method(
    request: Request,
    payload: PaymentMethodPayload,
    user: dict = Depends(get_current_user),
):
    """Validación DEFINITIVA de titularidad y registro del instrumento.

    Contrasta el instrumento contra la identidad verificada del usuario
    (snapshot `verified_identity` guardado en la BD al aprobar su KYC), nunca
    contra datos declarados por el cliente.
    """
    user_id = user["user_id"]

    # KYC progresivo: sin identidad verificada no hay contra qué validar la
    # titularidad. La app debe enrutar al usuario a su verificación de identidad.
    verified_identity = user.get("verified_identity")
    if not verified_identity:
        return JSONResponse(
            status_code=412,
            content={
                "error_code": "KYC_REQUIRED",
                "detail": (
                    "Para registrar un método de pago primero debes verificar tu "
                    "identidad (cédula y nombre). Completa tu verificación e "
                    "inténtalo de nuevo."
                ),
            },
        )

    try:
        verdict = await validate_payment_method_ownership(
            user_id=user_id,
            verified_identity=verified_identity,
            payment_method=payload.to_service_payload(),
        )
    except KYCServiceError as exc:
        return _kyc_error_response(exc)

    action = verdict.get("action")
    ownership = verdict.get("ownership", {})
    result = ownership.get("result")
    fingerprint = verdict.get("instrument_fingerprint", "")

    # ── Cláusula 6: tercer strike -> suspensión + revocación de JWTs ─────────
    if action == "SUSPEND_ACCOUNT":
        await _suspend_account(user_id, verdict)
        return JSONResponse(
            status_code=403,
            content={
                "error_code": "ACCOUNT_SUSPENDED",
                "account_status": ACCOUNT_SUSPENDED_PENDING_REVIEW,
                "detail": verdict.get("user_message"),
                "tc_clauses": verdict.get("tc_clauses", ["3.2", "6"]),
                "strikes_in_window": verdict.get("strikes_in_window"),
            },
        )

    # ── Cláusula 3.2: titularidad no coincide -> rechazo con strike ──────────
    if result == "MISMATCH":
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "OWNERSHIP_MISMATCH",
                "detail": verdict.get("user_message"),
                "tc_clauses": verdict.get("tc_clauses", ["3.2"]),
                "remaining_attempts": verdict.get("remaining_attempts"),
                "strikes_in_window": verdict.get("strikes_in_window"),
            },
        )

    # Mismo instrumento ya registrado y vigente en OTRA cuenta: se bloquea el
    # duplicado (la huella SHA-256 permite detectarlo sin guardar el dato en claro).
    duplicate = await db.payment_methods.find_one(
        {
            "instrument_fingerprint": fingerprint,
            "user_id": {"$ne": user_id},
            "status": {"$in": [PAYMENT_METHOD_ACTIVE, PAYMENT_METHOD_PENDING]},
        },
        {"_id": 0},
    )
    if duplicate:
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "INSTRUMENT_ALREADY_REGISTERED",
                "detail": (
                    "Este instrumento de pago ya está registrado en otra cuenta de "
                    "Xuve. Conforme a la cláusula 3.2, cada método de pago solo "
                    "puede estar asociado a la cuenta de su titular."
                ),
                "tc_clauses": ["3.2"],
            },
        )

    # ── MATCH -> ACTIVE (201) | MANUAL_REVIEW -> PENDING_VALIDATION (202) ────
    new_status = (
        PAYMENT_METHOD_ACTIVE if result == "MATCH" else PAYMENT_METHOD_PENDING
    )
    now = _now()
    existing = await db.payment_methods.find_one(
        {"user_id": user_id, "instrument_fingerprint": fingerprint}, {"_id": 0}
    )
    if existing:
        # Re-registro del mismo instrumento por el mismo usuario: se actualiza.
        await db.payment_methods.update_one(
            {"payment_method_id": existing["payment_method_id"]},
            {
                "$set": {
                    "status": new_status,
                    "holder_full_name": payload.holder_full_name,
                    "ownership_result": result,
                    "ownership_flags": ownership.get("flags", []),
                    "name_similarity": ownership.get("name_similarity"),
                    "kyc_request_id": verdict.get("request_id"),
                    "updated_at": now,
                }
            },
        )
        doc = await db.payment_methods.find_one(
            {"payment_method_id": existing["payment_method_id"]}, {"_id": 0}
        )
    else:
        doc = {
            "payment_method_id": f"pm_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "method_type": payload.method_type,
            "holder_full_name": payload.holder_full_name,
            # El instrumento NUNCA se guarda en claro: solo la vista enmascarada
            # para la UI y la huella SHA-256 para deduplicación/auditoría.
            "masked_identifier": _masked_identifier(payload),
            "bank_code": payload.bank_code,
            "instrument_fingerprint": fingerprint,
            "status": new_status,
            "ownership_result": result,
            "ownership_flags": ownership.get("flags", []),
            "name_similarity": ownership.get("name_similarity"),
            "kyc_request_id": verdict.get("request_id"),
            "created_at": now,
            "updated_at": now,
        }
        await db.payment_methods.insert_one(doc)
        if "_id" in doc:
            del doc["_id"]

    http_status = 201 if new_status == PAYMENT_METHOD_ACTIVE else 202
    return JSONResponse(
        status_code=http_status,
        content={
            "message": verdict.get("user_message"),
            "payment_method": _public_view(doc),
        },
    )


@router.get("")
async def list_payment_methods(user: dict = Depends(get_current_user)):
    """Instrumentos del usuario actual (vista enmascarada)."""
    methods = (
        await db.payment_methods.find({"user_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )
    return {"payment_methods": [_public_view(m) for m in methods]}

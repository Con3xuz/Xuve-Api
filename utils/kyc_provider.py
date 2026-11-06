"""
Abstracción del proveedor externo de KYC (verificación de identidad).
=====================================================================
Arquitectura lista para un proveedor real (Sumsub / Veriff / Didit, etc.) vía
webhooks, pero con un MODO MOCK para desarrollar y probar el flujo a costo cero.

- MODO MOCK (por defecto si no hay `KYC_PROVIDER_API_KEY`): NO se hace ninguna
  llamada a internet; la sesión de verificación se simula localmente y la
  decisión se dispara con el endpoint /api/kyc/simulate/{kyc_id}.
- PRODUCCIÓN: inyecta `KYC_PROVIDER_API_KEY` y `KYC_WEBHOOK_SECRET` en Secrets
  Manager. Con la API key presente, el modo mock se desactiva solo y solo falta
  implementar la llamada real en `start_verification` (marcada con TODO).

El webhook del proveedor llega a /api/kyc/webhook y se valida con firma HMAC.
"""

import os
import hmac
import hashlib
import uuid

import httpx

KYC_PROVIDER_API_KEY = os.environ.get("KYC_PROVIDER_API_KEY", "")
KYC_WEBHOOK_SECRET = os.environ.get("KYC_WEBHOOK_SECRET", "")
# Endpoint del proveedor para crear una sesión de verificación. Se inyecta junto
# con la API key cuando contratemos al proveedor (Secrets Manager). Si cambia el
# proveedor, solo cambian estas variables, no el código.
KYC_PROVIDER_BASE_URL = os.environ.get("KYC_PROVIDER_BASE_URL", "")
KYC_PROVIDER_CALLBACK_URL = os.environ.get(
    "KYC_PROVIDER_CALLBACK_URL", ""
)  # a dónde el proveedor enviará el webhook (= https://api.xuve.net/api/kyc/webhook)

# MOCK es OPT-IN explícito (apagado por defecto). En prod, sin esta variable, el
# modo mock NUNCA se activa: los endpoints de simulación quedan deshabilitados y
# la verificación real exige API key. Solo se enciende en local/dev poniendo
# KYC_MOCK_MODE=true. Esto evita que alguien se auto-apruebe el KYC en producción.
KYC_MOCK_MODE = os.environ.get("KYC_MOCK_MODE", "").lower() in ("1", "true", "yes")


def is_mock_mode() -> bool:
    return KYC_MOCK_MODE


async def start_verification(kyc_id: str, user: dict) -> dict:
    """
    Inicia una sesión de verificación con el proveedor.

    MOCK: devuelve una referencia simulada sin tocar internet.
    REAL: aquí iría el POST (httpx) al proveedor creando la sesión y devolviendo
    su id/URL de verificación. `kyc_id` se envía como `reference` para poder
    correlacionar el webhook de vuelta.
    """
    if KYC_MOCK_MODE:
        return {
            "provider": "mock",
            "provider_ref": f"mock_{uuid.uuid4().hex[:12]}",
            "mock": True,
        }

    # PRODUCCIÓN: crea la sesión contra el proveedor real. Solo requiere que estén
    # configuradas KYC_PROVIDER_API_KEY y KYC_PROVIDER_BASE_URL (Secrets Manager).
    # El payload sigue el patrón común (Sumsub/Veriff/Didit): se manda `reference`
    # = kyc_id para correlacionar el webhook de vuelta. Ajustar el mapeo de campos
    # al esquema exacto del proveedor cuando tengamos su documentación.
    if not (KYC_PROVIDER_API_KEY and KYC_PROVIDER_BASE_URL):
        raise NotImplementedError(
            "KYC real no configurado: faltan KYC_PROVIDER_API_KEY / KYC_PROVIDER_BASE_URL"
        )

    payload = {
        "reference": kyc_id,
        "externalUserId": user.get("user_id"),
        "email": user.get("email"),
        "levelName": user.get("pending_role") or user.get("role") or "user",
    }
    if KYC_PROVIDER_CALLBACK_URL:
        payload["callbackUrl"] = KYC_PROVIDER_CALLBACK_URL

    headers = {
        "Authorization": f"Bearer {KYC_PROVIDER_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{KYC_PROVIDER_BASE_URL.rstrip('/')}/verification-sessions",
            json=payload,
            headers=headers,
        )
    resp.raise_for_status()
    data = resp.json()
    return {
        "provider": "external",
        # Acepta varios nombres habituales del id de sesión del proveedor.
        "provider_ref": data.get("id") or data.get("sessionId") or data.get("reference"),
        "verification_url": data.get("url") or data.get("verificationUrl"),
        "mock": False,
    }


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """
    Verifica la firma HMAC-SHA256 del webhook del proveedor.
    Si no hay secreto configurado, solo se acepta en modo mock (local).
    """
    if not KYC_WEBHOOK_SECRET:
        return KYC_MOCK_MODE
    expected = hmac.new(
        KYC_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


# ═════════════════════════════════════════════════════════════════════════════
# Cliente del microservicio propio xuve-kyc-service (KYC progresivo + motor de
# titularidad de métodos de pago, T&C cláusulas 3.2 y 6).
# ═════════════════════════════════════════════════════════════════════════════
# Variables INDEPENDIENTES de las del proveedor webhook de arriba: la presencia
# de KYC_PROVIDER_API_KEY afecta al modo mock del flujo legacy y no debe
# mezclarse con la autenticación del microservicio interno.
KYC_SERVICE_URL = os.environ.get("KYC_SERVICE_URL", "http://localhost:8010").rstrip("/")
KYC_SERVICE_API_KEY = os.environ.get("KYC_SERVICE_API_KEY", "")
# Secreto compartido para verificar la firma HMAC-SHA256 de las RESPUESTAS del
# microservicio (header X-KYC-Signature sobre el cuerpo exacto).
KYC_SERVICE_HMAC_SECRET = os.environ.get("KYC_SERVICE_HMAC_SECRET", "")
KYC_SERVICE_TIMEOUT = float(os.environ.get("KYC_SERVICE_TIMEOUT", "30"))

KYC_SERVICE_API_KEY_HEADER = "X-KYC-API-KEY"
KYC_SERVICE_SIGNATURE_HEADER = "X-KYC-Signature"


class KYCServiceError(Exception):
    """Fallo de comunicación o de integridad con xuve-kyc-service.

    Fail-closed: quien la capture debe abortar la operación (nunca aprobar por
    defecto un método de pago o una verificación).
    """

    def __init__(self, detail: str, status_code: int = 502):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def kyc_service_configured() -> bool:
    """True si el backend tiene credenciales para hablar con xuve-kyc-service."""
    return bool(KYC_SERVICE_API_KEY)


def verify_kyc_service_signature(raw_body: bytes, signature: str | None) -> bool:
    """Verifica la firma HMAC-SHA256 que el microservicio pone en X-KYC-Signature.

    Con secreto configurado la firma es OBLIGATORIA (una respuesta sin firma o
    con firma inválida se descarta). Sin secreto configurado no hay nada que
    verificar (entornos locales sin HMAC_SIGNING_SECRET en el microservicio).
    """
    if not KYC_SERVICE_HMAC_SECRET:
        return True
    expected = hmac.new(
        KYC_SERVICE_HMAC_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def _kyc_service_check_response(resp: httpx.Response) -> dict:
    """Valida firma HMAC y decodifica JSON. Lanza KYCServiceError si algo falla."""
    signature = resp.headers.get(KYC_SERVICE_SIGNATURE_HEADER)
    if not verify_kyc_service_signature(resp.content, signature):
        raise KYCServiceError(
            "Firma HMAC inválida en la respuesta del servicio de KYC; respuesta descartada."
        )
    try:
        return resp.json()
    except ValueError:
        raise KYCServiceError("Respuesta no-JSON del servicio de KYC.")


async def _kyc_service_post_json(path: str, payload: dict) -> tuple[int, dict]:
    """POST JSON autenticado al microservicio. Devuelve (status_code, body)."""
    if not kyc_service_configured():
        raise KYCServiceError(
            "Servicio de KYC no configurado (falta KYC_SERVICE_API_KEY).", 503
        )
    headers = {KYC_SERVICE_API_KEY_HEADER: KYC_SERVICE_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=KYC_SERVICE_TIMEOUT) as client:
            resp = await client.post(
                f"{KYC_SERVICE_URL}{path}", json=payload, headers=headers
            )
    except httpx.HTTPError as exc:
        raise KYCServiceError(f"Servicio de KYC inaccesible: {exc.__class__.__name__}")
    return resp.status_code, _kyc_service_check_response(resp)


async def pre_validate_payment_method(draft: dict) -> tuple[int, dict]:
    """Pre-validación sintáctica en vivo (la app la usa mientras el usuario tipea).

    Passthrough: devuelve el status y el cuerpo tal cual (200 con formatted_data
    canónico, o 422 con la lista de errores por campo).
    """
    return await _kyc_service_post_json("/api/v1/payment-methods/pre-validate", draft)


async def validate_payment_method_ownership(
    user_id: str, verified_identity: dict, payment_method: dict
) -> dict:
    """Validación definitiva de titularidad contra el motor del microservicio.

    Envía el snapshot de identidad verificada guardado en la BD del usuario
    (nunca datos declarados por el cliente). El veredicto llega siempre como
    200 tipado; cualquier otro status es un error de integración.
    """
    status_code, body = await _kyc_service_post_json(
        "/api/v1/payment-methods/validate",
        {
            "user_id": user_id,
            "verified_identity": verified_identity,
            "payment_method": payment_method,
        },
    )
    if status_code != 200:
        raise KYCServiceError(
            f"El motor de titularidad respondió {status_code}: "
            f"{body.get('detail') or body.get('error') or body}"
        )
    return body


async def verify_role_dossier(
    entity: str, user_id: str, files: dict[str, tuple[str, bytes, str]]
) -> dict:
    """Envía el expediente completo a /api/v1/verify/{driver|merchant}.

    `files` mapea nombre de campo -> (filename, contenido, content_type).
    Devuelve el VerificationResponse del microservicio (status APPROVED /
    MANUAL_REVIEW / REJECTED + extracted_data).
    """
    if entity not in ("driver", "merchant"):
        raise ValueError(f"Entidad de verificación no soportada: {entity}")
    if not kyc_service_configured():
        raise KYCServiceError(
            "Servicio de KYC no configurado (falta KYC_SERVICE_API_KEY).", 503
        )
    headers = {KYC_SERVICE_API_KEY_HEADER: KYC_SERVICE_API_KEY}
    try:
        # El expediente incluye video de prueba de vida + OCR multimodal:
        # timeout amplio e independiente del de las llamadas JSON.
        async with httpx.AsyncClient(timeout=max(KYC_SERVICE_TIMEOUT, 120.0)) as client:
            resp = await client.post(
                f"{KYC_SERVICE_URL}/api/v1/verify/{entity}",
                data={"user_id": user_id},
                files=files,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise KYCServiceError(f"Servicio de KYC inaccesible: {exc.__class__.__name__}")
    body = _kyc_service_check_response(resp)
    if resp.status_code != 200:
        raise KYCServiceError(
            f"La verificación KYC respondió {resp.status_code}: "
            f"{body.get('detail') or body.get('error') or body}"
        )
    return body

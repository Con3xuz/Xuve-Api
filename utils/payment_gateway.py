"""
Pasarela de pago — Suscripción SaaS de $1/día (modelo P2P de Xuve).
===================================================================
Xuve opera como SaaS: la plataforma NUNCA toca el dinero de viajes ni ventas
(eso es directo entre conductor/negocio y cliente). El ÚNICO cobro de la
plataforma es la suscripción diaria fija de $1 que activa la cuenta por 24h.

- MODO MOCK (por defecto si no hay `PAYMENTS_API_KEY`): aprueba el cobro al
  instante, sin tocar internet, para probar el flujo completo a costo cero.
- PRODUCCIÓN: inyecta `PAYMENTS_API_KEY` y `PAYMENTS_WEBHOOK_SECRET` en Secrets
  Manager; el cobro real crea un intent en el banco y se resuelve por webhook.

El webhook del banco llega a /api/payments/webhook y se valida con firma HMAC.
"""

import os
import hmac
import hashlib

import httpx

PAYMENTS_API_KEY = os.environ.get("PAYMENTS_API_KEY", "")
PAYMENTS_WEBHOOK_SECRET = os.environ.get("PAYMENTS_WEBHOOK_SECRET", "")
# Endpoint del banco/pasarela para crear el cobro y URL de retorno del webhook.
# Se inyectan al contratar el banco (Secrets Manager). Cambiar de banco = cambiar
# estas variables, sin tocar el código.
PAYMENTS_BASE_URL = os.environ.get("PAYMENTS_BASE_URL", "")
PAYMENTS_CALLBACK_URL = os.environ.get(
    "PAYMENTS_CALLBACK_URL", ""
)  # = https://api.xuve.net/api/payments/webhook

# MOCK es OPT-IN explícito (apagado por defecto). En prod, sin esta variable, el
# cobro simulado NUNCA se activa: /subscribe responde 503 hasta tener pasarela
# real y /simulate queda deshabilitado. Solo se enciende en local/dev poniendo
# PAYMENTS_MOCK_MODE=true. Evita activaciones gratis en producción.
PAYMENTS_MOCK_MODE = os.environ.get("PAYMENTS_MOCK_MODE", "").lower() in ("1", "true", "yes")


def is_mock_mode() -> bool:
    return PAYMENTS_MOCK_MODE


async def create_charge(reference: str, amount: float, user: dict) -> dict:
    """
    Crea un cobro de suscripción.

    MOCK: lo aprueba al instante (status 'approved').
    REAL: crearía el intent en el banco y devolvería 'pending' + datos de
    checkout; el resultado definitivo llega por webhook.
    """
    if PAYMENTS_MOCK_MODE:
        return {
            "status": "approved",
            "reference": reference,
            "provider": "mock",
            "mock": True,
        }

    # PRODUCCIÓN: crea el cobro contra el banco/pasarela real. Devuelve 'pending'
    # + datos de checkout; el resultado definitivo llega por /api/payments/webhook
    # (verificado con firma HMAC). Solo requiere PAYMENTS_API_KEY + PAYMENTS_BASE_URL.
    if not (PAYMENTS_API_KEY and PAYMENTS_BASE_URL):
        raise NotImplementedError(
            "Pago real no configurado: faltan PAYMENTS_API_KEY / PAYMENTS_BASE_URL"
        )

    payload = {
        "reference": reference,
        "amount": amount,
        "currency": "USD",
        "customer": {"id": user.get("user_id"), "email": user.get("email")},
    }
    if PAYMENTS_CALLBACK_URL:
        payload["callbackUrl"] = PAYMENTS_CALLBACK_URL

    headers = {
        "Authorization": f"Bearer {PAYMENTS_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{PAYMENTS_BASE_URL.rstrip('/')}/charges", json=payload, headers=headers
        )
    resp.raise_for_status()
    data = resp.json()
    return {
        "status": (data.get("status") or "pending").lower(),
        "reference": reference,
        "provider": "bank",
        "checkout": data.get("checkoutUrl") or data.get("url"),
        "mock": False,
    }


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Verifica la firma HMAC-SHA256 del webhook bancario. Sin secreto, solo mock."""
    if not PAYMENTS_WEBHOOK_SECRET:
        return PAYMENTS_MOCK_MODE
    expected = hmac.new(
        PAYMENTS_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")

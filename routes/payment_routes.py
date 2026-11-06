"""
Pagos — Suscripción SaaS de $1/día (Xuve P2P).
==============================================
La plataforma SOLO cobra esta suscripción, que activa la cuenta del socio
(conductor/negocio) por 24h. NO toca el dinero de viajes/ventas: eso es directo
entre las partes con sus propios métodos de pago.

Activador principal del servicio = el TIEMPO de suscripción (`access_expires_at`
en el usuario). Cada pago de $1 suma 24h a partir de la expiración vigente
(o desde ahora si ya venció). La billetera interna (`wallet_balance`) queda solo
como saldo de respaldo / crédito a favor.

Pasarela bancaria en modo mock (ver utils/payment_gateway.py); lista para
webhooks reales sin tocar esta lógica.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta
import uuid
import json

from utils.database import db
from utils.auth import get_current_user
from utils.financial_config import get_daily_subscription_fee
from utils.payment_gateway import create_charge, verify_webhook_signature, is_mock_mode
from utils.wallet_ops import credit_balance_atomic

from utils.ratelimit import limiter

router = APIRouter(prefix="/payments", tags=["Payments"])

ACCESS_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def _extend_access(user_id: str, hours: int = ACCESS_HOURS) -> str:
    """Extiende `access_expires_at`: base = max(ahora, expiración actual) + horas.
    Así, pagar varios días seguidos acumula tiempo en vez de perderlo."""
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    base = _now()
    current = _parse_iso((user or {}).get("access_expires_at"))
    if current and current > base:
        base = current
    new_exp = (base + timedelta(hours=hours)).isoformat()
    await db.users.update_one(
        {"user_id": user_id}, {"$set": {"access_expires_at": new_exp}}
    )
    return new_exp


async def _apply_successful_payment(payment: dict) -> dict:
    """Marca el pago como pagado y extiende el acceso 24h. Idempotente
    (si ya estaba pagado, no vuelve a sumar tiempo)."""
    if payment.get("status") == "paid":
        return {
            "reference": payment["reference"],
            "status": "paid",
            "access_expires_at": payment.get("access_expires_at"),
            "already_processed": True,
        }
    new_exp = await _extend_access(payment["user_id"])
    await db.subscription_payments.update_one(
        {"reference": payment["reference"]},
        {"$set": {
            "status": "paid",
            "paid_at": _now().isoformat(),
            "access_expires_at": new_exp,
        }},
    )
    return {
        "reference": payment["reference"],
        "status": "paid",
        "access_expires_at": new_exp,
    }


@router.post("/subscribe")
@limiter.limit("10/minute")
async def subscribe(request: Request, user: dict = Depends(get_current_user)):
    """
    Inicia el cobro de la suscripción diaria ($1) que activa la cuenta 24h.
    En modo mock, el cobro se aprueba al instante y el acceso se extiende ya.
    En real, queda 'pending' hasta que el banco confirme por webhook.
    """
    amount = await get_daily_subscription_fee()
    reference = f"sub_{uuid.uuid4().hex[:16]}"
    payment_doc = {
        "reference": reference,
        "user_id": user["user_id"],
        "amount": amount,
        "currency": "USD",
        "status": "pending",
        "created_at": _now().isoformat(),
    }
    await db.subscription_payments.insert_one(payment_doc)

    try:
        charge = await create_charge(reference, amount, user)
    except NotImplementedError:
        # Pasarela real aún no implementada y mock apagado (prod sin configurar).
        await db.subscription_payments.update_one(
            {"reference": reference}, {"$set": {"status": "unavailable"}}
        )
        raise HTTPException(
            status_code=503, detail="Pasarela de pago no configurada todavía"
        )

    if charge.get("status") == "approved":
        result = await _apply_successful_payment(payment_doc)
        return {"success": True, "mock": charge.get("mock", False), "amount": amount, **result}

    # Pasarela real: pendiente hasta el webhook bancario.
    return {
        "success": True,
        "status": "pending",
        "reference": reference,
        "amount": amount,
        "checkout": charge.get("checkout"),
    }


@router.post("/webhook")
async def payments_webhook(request: Request):
    """
    Webhook de la pasarela bancaria. Verifica firma HMAC y, si el pago fue
    exitoso, extiende el acceso 24h. Lo llama el banco (sin sesión, con firma).
    """
    raw = await request.body()
    signature = request.headers.get("X-Signature", "")
    if not verify_webhook_signature(raw, signature):
        raise HTTPException(status_code=401, detail="Firma de webhook inválida")

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload inválido")

    reference = payload.get("reference")
    status = (payload.get("status") or "").lower()
    if not reference:
        raise HTTPException(status_code=400, detail="reference requerido")
    approved = status in ("approved", "paid", "success", "completed")

    # Recargas de billetera (referencia rcg_*) -> acreditan wallet_balance.
    if reference.startswith("rcg_"):
        return await _apply_recharge_webhook(reference, approved)

    # Suscripción SaaS diaria.
    payment = await db.subscription_payments.find_one({"reference": reference}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    if approved:
        return await _apply_successful_payment(payment)

    await db.subscription_payments.update_one(
        {"reference": reference}, {"$set": {"status": "failed"}}
    )
    return {"reference": reference, "status": "failed"}


async def _apply_recharge_webhook(gateway_reference: str, approved: bool) -> dict:
    """Acredita una recarga de billetera al confirmar el banco. Idempotente:
    solo acredita si la transacción sigue 'pending'."""
    tx = await db.transactions.find_one(
        {"gateway_reference": gateway_reference, "type": "recharge"}, {"_id": 0}
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Recarga no encontrada")
    if tx.get("status") == "completed":
        return {"reference": gateway_reference, "status": "completed", "already_processed": True}

    if not approved:
        await db.transactions.update_one(
            {"gateway_reference": gateway_reference}, {"$set": {"status": "failed"}}
        )
        return {"reference": gateway_reference, "status": "failed"}

    await credit_balance_atomic(tx["user_id"], tx["amount_usd"])
    await db.transactions.update_one(
        {"gateway_reference": gateway_reference},
        {"$set": {"status": "completed", "paid_at": _now().isoformat()}},
    )
    return {"reference": gateway_reference, "status": "completed"}


@router.post("/simulate/{reference}")
async def simulate_payment(reference: str, user: dict = Depends(get_current_user)):
    """SOLO MOCK: simula la notificación del banco aprobando un pago pendiente,
    para probar el flujo completo en local. Deshabilitado con pasarela real."""
    if not is_mock_mode():
        raise HTTPException(
            status_code=403, detail="Simulación deshabilitada (pasarela real activa)"
        )
    payment = await db.subscription_payments.find_one({"reference": reference}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return await _apply_successful_payment(payment)


@router.get("/subscription-status")
async def subscription_status(user: dict = Depends(get_current_user)):
    """Estado de la suscripción SaaS: si la cuenta está activa según el tiempo
    restante (`access_expires_at`). La billetera va aparte como respaldo."""
    u = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    exp = (u or {}).get("access_expires_at")
    exp_dt = _parse_iso(exp)
    seconds_left = int((exp_dt - _now()).total_seconds()) if exp_dt else 0
    return {
        "active": seconds_left > 0,
        "access_expires_at": exp,
        "seconds_remaining": max(0, seconds_left),
        "daily_fee": await get_daily_subscription_fee(),
        "wallet_balance": (u or {}).get("wallet_balance", 0.0),  # respaldo
        "currency": "USD",
        "mock_gateway": is_mock_mode(),
    }

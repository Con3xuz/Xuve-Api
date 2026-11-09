"""Controlador de wallet - Validaciones y lógica de negocio."""
from models import *
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timezone
import uuid

from models import db
from utils.auth import get_current_user
from utils.payment_gateway import is_mock_mode, create_charge
from utils.wallet_ops import (
    debit_available_atomic,
    hold_funds_atomic,
    InsufficientFunds,
)
from controllers.validators import WalletRecharge, WalletWithdraw, WalletHold



async def get_wallet_balance(user: dict = Depends(get_current_user)):
    return {"balance": user.get("wallet_balance", 0.0), "currency": "USD"}


async def recharge_wallet(
    recharge: WalletRecharge, user: dict = Depends(get_current_user)
):
    rate = await ExchangeRateModel.find_one({}, {"_id": 0}, sort=[("updated_at", -1)])
    usd_rate = rate.get("usd_to_bs", 50.0) if rate else 50.0

    amount_usd = recharge.amount_bs / usd_rate

    # Referencia ÚNICA de pasarela para correlacionar el webhook bancario.
    gateway_reference = f"rcg_{uuid.uuid4().hex[:16]}"
    transaction = {
        "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "amount_usd": amount_usd,
        "amount_bs": recharge.amount_bs,
        "type": "recharge",
        "status": "pending",
        "payment_method": recharge.payment_method,
        "reference": recharge.reference,
        "gateway_reference": gateway_reference,
        "description": f"Recarga via {recharge.payment_method}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await TransactionModel.insert_one(transaction)

    # SEGURIDAD: la recarga NO se auto-acredita. En producción queda 'pending'
    # hasta que el banco confirme el pago por webhook (/api/payments/webhook,
    # verificado con firma HMAC, acredita vía credit_balance_atomic). Solo en modo
    # mock (dev/test) se acredita al instante para probar el flujo a costo cero.
    if is_mock_mode():
        await UserModel.update_one(
            {"user_id": user["user_id"]}, {"$inc": {"wallet_balance": amount_usd}}
        )
        await TransactionModel.update_one(
            {"transaction_id": transaction["transaction_id"]},
            {"$set": {"status": "completed"}},
        )
        updated_user = await UserModel.find_one({"user_id": user["user_id"]}, {"_id": 0})
        return {
            "message": "Recarga exitosa",
            "status": "completed",
            "amount_usd": amount_usd,
            "new_balance": updated_user.get("wallet_balance", 0),
            "mock": True,
        }

    # Producción: inicia el cobro real contra el banco. Acreditación por webhook.
    try:
        charge = await create_charge(gateway_reference, amount_usd, user)
    except NotImplementedError:
        # Banco aún no configurado (sin PAYMENTS_API_KEY/BASE_URL): marca la
        # recarga como no disponible y responde 503 (no rompe con un 500).
        await TransactionModel.update_one(
            {"transaction_id": transaction["transaction_id"]},
            {"$set": {"status": "unavailable"}},
        )
        raise HTTPException(
            status_code=503, detail="Pasarela de pago no configurada todavía"
        )
    return {
        "message": "Recarga registrada; pendiente de confirmación del banco.",
        "status": "pending",
        "amount_usd": amount_usd,
        "transaction_id": transaction["transaction_id"],
        "reference": gateway_reference,
        "checkout": charge.get("checkout"),
    }


async def withdraw_wallet(
    withdraw: WalletWithdraw, user: dict = Depends(get_current_user)
):
    # Débito ATÓMICO sobre el disponible (balance - held): el chequeo y el
    # descuento ocurren en el mismo UPDATE -> sin condición de carrera y sin
    # poder retirar fondos congelados como garantía.
    try:
        await debit_available_atomic(user["user_id"], withdraw.amount_usd)
    except InsufficientFunds:
        raise HTTPException(status_code=400, detail="Saldo disponible insuficiente")

    transaction = {
        "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "amount_usd": -withdraw.amount_usd,
        "type": "withdraw",
        "status": "pending",
        "bank_name": withdraw.bank_name,
        "phone": withdraw.phone,
        "cedula": withdraw.cedula,
        "description": f"Retiro a Pago Móvil - {withdraw.bank_name}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await TransactionModel.insert_one(transaction)

    return {
        "message": "Solicitud de retiro enviada",
        "status": "pending",
        "transaction_id": transaction["transaction_id"],
    }


async def get_transactions(user: dict = Depends(get_current_user)):
    transactions = (
        await TransactionModel.find({"user_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return transactions


# ==================== WALLET HOLD SYSTEM (Para garantías) ====================


async def create_wallet_hold(
    hold_data: WalletHold, user: dict = Depends(get_current_user)
):
    """Congelar fondos para garantías (Rent a Car, etc.)"""
    # Congelado ATÓMICO: chequea disponible e incrementa wallet_held en el mismo
    # UPDATE -> sin condición de carrera.
    try:
        await hold_funds_atomic(user["user_id"], hold_data.amount_usd)
    except InsufficientFunds:
        raise HTTPException(
            status_code=400, detail="Saldo disponible insuficiente"
        )

    hold_doc = {
        "hold_id": f"hold_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "amount_usd": hold_data.amount_usd,
        "reason": hold_data.reason,
        "reference_id": hold_data.reference_id,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await WalletHoldModel.insert_one(hold_doc)

    if "_id" in hold_doc:
        del hold_doc["_id"]

    return {"message": "Fondos congelados exitosamente", "hold": hold_doc}


async def release_wallet_hold(hold_id: str, user: dict = Depends(get_current_user)):
    """Liberar fondos congelados (solo el dueño del hold)."""
    # SEGURIDAD (IDOR): el hold debe pertenecer al usuario autenticado.
    hold = await WalletHoldModel.find_one(
        {"hold_id": hold_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not hold:
        raise HTTPException(status_code=404, detail="Hold no encontrado")

    if hold["status"] != "active":
        raise HTTPException(status_code=400, detail="Este hold ya fue procesado")

    await WalletHoldModel.update_one(
        {"hold_id": hold_id},
        {
            "$set": {
                "status": "released",
                "released_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    await UserModel.update_one(
        {"user_id": hold["user_id"]}, {"$inc": {"wallet_held": -hold["amount_usd"]}}
    )

    return {"message": "Fondos liberados", "amount": hold["amount_usd"]}


async def charge_wallet_hold(
    hold_id: str, amount: float = None, user: dict = Depends(get_current_user)
):
    """Cobrar fondos del hold (para penalizaciones, etc.)"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede cobrar holds")

    hold = await WalletHoldModel.find_one({"hold_id": hold_id}, {"_id": 0})
    if not hold:
        raise HTTPException(status_code=404, detail="Hold no encontrado")

    charge_amount = amount if amount else hold["amount_usd"]
    if charge_amount > hold["amount_usd"]:
        charge_amount = hold["amount_usd"]

    await UserModel.update_one(
        {"user_id": hold["user_id"]},
        {
            "$inc": {
                "wallet_balance": -charge_amount,
                "wallet_held": -hold["amount_usd"],
            }
        },
    )

    await WalletHoldModel.update_one(
        {"hold_id": hold_id},
        {
            "$set": {
                "status": "charged",
                "charged_amount": charge_amount,
                "charged_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    await TransactionModel.insert_one(
        {
            "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
            "user_id": hold["user_id"],
            "amount_usd": -charge_amount,
            "type": "hold_charge",
            "status": "completed",
            "description": f"Cargo por {hold['reason']} - {hold['reference_id']}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    return {"message": "Fondos cobrados", "charged": charge_amount}


async def get_wallet_holds(user: dict = Depends(get_current_user)):
    """Obtener holds activos del usuario"""
    holds = await WalletHoldModel.find(
        {"user_id": user["user_id"], "status": "active"}, {"_id": 0}
    ).to_list(100)
    return holds


# Exchange Rate endpoints


async def get_exchange_rate():
    """
    Obtener tasa de cambio actual.
    Lee primero de platform_config (configuración del admin), luego de exchange_rates (legacy).
    """
    # Primero intentar leer de platform_config (nuevo sistema del admin)
    config = await PlatformConfigModel.find_one({"type": "financial"}, {"_id": 0})
    if config and config.get("exchange_rate"):
        return {
            "usd_to_bs": config["exchange_rate"],
            "updated_at": config.get(
                "updated_at", datetime.now(timezone.utc).isoformat()
            ),
            "source": "platform_config",
        }

    # Fallback a exchange_rates (legacy)
    rate = await ExchangeRateModel.find_one({}, {"_id": 0}, sort=[("updated_at", -1)])
    if rate:
        return {
            "usd_to_bs": rate.get("usd_to_bs", 50.0),
            "updated_at": rate.get(
                "updated_at", datetime.now(timezone.utc).isoformat()
            ),
            "source": "exchange_rates",
        }

    # Default
    return {
        "usd_to_bs": 50.0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "default",
    }


async def set_exchange_rate(
    rate: float = Body(..., embed=True), user: dict = Depends(get_current_user)
):
    """
    Actualizar tasa de cambio.
    Actualiza tanto platform_config como exchange_rates para compatibilidad.
    """
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    now = datetime.now(timezone.utc).isoformat()

    # Actualizar en platform_config (nuevo sistema)
    await PlatformConfigModel.update_one(
        {"type": "financial"},
        {
            "$set": {
                "exchange_rate": rate,
                "updated_at": now,
                "updated_by": user["user_id"],
            }
        },
        upsert=True,
    )

    # También guardar en exchange_rates (legacy - para compatibilidad)
    rate_doc = {
        "rate_id": f"rate_{uuid.uuid4().hex[:8]}",
        "usd_to_bs": rate,
        "updated_at": now,
        "updated_by": user["user_id"],
    }
    await ExchangeRateModel.insert_one(rate_doc)

    return {
        "usd_to_bs": rate,
        "updated_at": now,
        "message": "Tasa actualizada en toda la plataforma",
    }

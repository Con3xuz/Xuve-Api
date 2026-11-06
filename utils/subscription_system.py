"""
OMNI - Sistema de Suscripción Diaria para Socios
================================================
Nuevo modelo económico: $1 USD por día de trabajo.

Flujo:
1. Socio recarga saldo en su billetera
2. Al presionar "ACTIVARME", se verifica saldo >= $1
3. Si tiene saldo, se descuenta $1 y queda activo hasta medianoche
4. Puede desconectarse y reconectarse sin costo adicional el mismo día
5. Después de medianoche, debe activarse de nuevo (otro $1)

Beneficios para nuevos socios:
- 3 días gratis desde la primera activación
"""

from datetime import datetime, timezone, timedelta
from utils.database import db
import uuid

# Configuración del sistema de suscripción
DAILY_SUBSCRIPTION_FEE = 1.00  # $1 USD por día
FREE_TRIAL_DAYS = 3  # 3 días gratis para nuevos socios


async def get_daily_fee() -> float:
    """Obtener el fee diario de suscripción"""
    config = await db.platform_config.find_one({"type": "subscription"}, {"_id": 0})
    if config and "daily_fee" in config:
        return config["daily_fee"]
    return DAILY_SUBSCRIPTION_FEE


async def get_free_trial_days() -> int:
    """Obtener la cantidad de días de prueba gratis"""
    config = await db.platform_config.find_one({"type": "subscription"}, {"_id": 0})
    if config and "free_trial_days" in config:
        return config["free_trial_days"]
    return FREE_TRIAL_DAYS


async def get_user_first_activation(user_id: str) -> datetime | None:
    """Obtener la fecha de primera activación del usuario"""
    record = await db.subscription_history.find_one(
        {"user_id": user_id}, {"_id": 0, "first_activation": 1}
    )
    if record and record.get("first_activation"):
        return datetime.fromisoformat(record["first_activation"].replace("Z", "+00:00"))
    return None


async def is_in_free_trial(user_id: str) -> tuple[bool, int]:
    """
    Verificar si el usuario está en período de prueba gratis.
    Retorna (está_en_trial, días_restantes)
    """
    first_activation = await get_user_first_activation(user_id)

    if first_activation is None:
        # Nunca se ha activado - tendrá los días gratis cuando se active
        free_days = await get_free_trial_days()
        return True, free_days

    free_days = await get_free_trial_days()
    now = datetime.now(timezone.utc)
    trial_end = first_activation + timedelta(days=free_days)

    if now < trial_end:
        days_remaining = (trial_end - now).days + 1
        return True, days_remaining

    return False, 0


async def has_active_subscription_today(user_id: str) -> bool:
    """
    Verificar si el usuario ya pagó la suscripción de hoy.
    La suscripción es válida desde que se activa hasta medianoche.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    subscription = await db.daily_subscriptions.find_one(
        {"user_id": user_id, "date": today_start.isoformat(), "status": "active"}
    )

    return subscription is not None


async def get_subscription_status(user_id: str) -> dict:
    """
    Obtener el estado completo de la suscripción del usuario.
    """
    in_trial, trial_days = await is_in_free_trial(user_id)
    has_today = await has_active_subscription_today(user_id)
    daily_fee = await get_daily_fee()

    # Obtener saldo del usuario
    wallet = await db.wallets.find_one({"user_id": user_id}, {"_id": 0, "balance": 1})
    balance = wallet.get("balance", 0) if wallet else 0

    can_activate = has_today or in_trial or balance >= daily_fee

    return {
        "has_active_subscription": has_today,
        "in_free_trial": in_trial,
        "trial_days_remaining": trial_days if in_trial else 0,
        "daily_fee": daily_fee,
        "balance": balance,
        "can_activate": can_activate,
        "reason": None if can_activate else "insufficient_balance",
    }


async def activate_subscription(user_id: str, user_name: str = "Usuario") -> dict:
    """
    Activar la suscripción diaria del usuario.

    Retorna:
    - success: True/False
    - message: Mensaje descriptivo
    - charged: Monto cobrado (0 si está en trial o ya pagó hoy)
    - subscription_id: ID de la suscripción
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. Verificar si ya tiene suscripción activa hoy
    existing = await db.daily_subscriptions.find_one(
        {"user_id": user_id, "date": today_start.isoformat(), "status": "active"}
    )

    if existing:
        return {
            "success": True,
            "message": "Ya tienes suscripción activa para hoy",
            "charged": 0,
            "subscription_id": existing.get("subscription_id"),
            "valid_until": "23:59:59",
        }

    daily_fee = await get_daily_fee()

    # 2. Verificar si está en período de prueba
    in_trial, trial_days = await is_in_free_trial(user_id)
    first_activation = await get_user_first_activation(user_id)

    # Si es la primera activación, registrarla
    if first_activation is None:
        await db.subscription_history.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "first_activation": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            },
            upsert=True,
        )
        in_trial = True
        trial_days = await get_free_trial_days()

    charged_amount = 0

    # 3. Si está en trial, no cobra
    if in_trial:
        charged_amount = 0
    else:
        # 4. Verificar y descontar saldo
        wallet = await db.wallets.find_one({"user_id": user_id})

        if not wallet or wallet.get("balance", 0) < daily_fee:
            return {
                "success": False,
                "message": f"Saldo insuficiente. Necesitas ${daily_fee:.2f} USD para activarte. Recarga tu billetera.",
                "charged": 0,
                "subscription_id": None,
                "balance_required": daily_fee,
                "current_balance": wallet.get("balance", 0) if wallet else 0,
            }

        # Descontar del saldo
        new_balance = wallet["balance"] - daily_fee
        await db.wallets.update_one(
            {"user_id": user_id},
            {"$set": {"balance": new_balance, "updated_at": now.isoformat()}},
        )
        charged_amount = daily_fee

        # Registrar transacción
        transaction = {
            "transaction_id": f"sub_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "type": "subscription_fee",
            "amount": -daily_fee,
            "description": f"Suscripción diaria OMNI - {today_start.strftime('%d/%m/%Y')}",
            "balance_after": new_balance,
            "created_at": now.isoformat(),
        }
        await db.transactions.insert_one(transaction)

    # 5. Crear registro de suscripción del día
    subscription_id = f"dsub_{uuid.uuid4().hex[:12]}"
    subscription = {
        "subscription_id": subscription_id,
        "user_id": user_id,
        "user_name": user_name,
        "date": today_start.isoformat(),
        "activated_at": now.isoformat(),
        "valid_until": today_start.replace(hour=23, minute=59, second=59).isoformat(),
        "status": "active",
        "amount_charged": charged_amount,
        "is_trial": in_trial,
        "trial_day": (
            (await get_free_trial_days()) - trial_days + 1 if in_trial else None
        ),
    }
    await db.daily_subscriptions.insert_one(subscription)

    # Mensaje según si es trial o pago
    if in_trial:
        message = f"¡Activado! Día {subscription['trial_day']} de {await get_free_trial_days()} gratis. Disfruta tu día de trabajo."
    else:
        message = f"¡Activado! Se descontó ${daily_fee:.2f} de tu billetera. Válido hasta las 23:59."

    return {
        "success": True,
        "message": message,
        "charged": charged_amount,
        "subscription_id": subscription_id,
        "valid_until": "23:59:59",
        "is_trial": in_trial,
        "trial_days_remaining": trial_days - 1 if in_trial else 0,
    }


async def deactivate_subscription(user_id: str) -> dict:
    """
    Desactivar la suscripción (el usuario se desconecta).
    Nota: NO reembolsa el dinero, puede volver a conectarse hasta medianoche.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # No eliminamos la suscripción, solo marcamos que se desconectó
    # (puede volver a conectarse sin pagar de nuevo hoy)
    await db.daily_subscriptions.update_one(
        {"user_id": user_id, "date": today_start.isoformat()},
        {"$set": {"last_disconnection": now.isoformat()}},
    )

    return {
        "success": True,
        "message": "Desconectado. Puedes volver a activarte hoy sin costo adicional.",
    }


async def get_subscription_stats() -> dict:
    """
    Obtener estadísticas de suscripciones para el admin.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Suscripciones activas hoy
    active_today = await db.daily_subscriptions.count_documents(
        {"date": today_start.isoformat(), "status": "active"}
    )

    # Ingresos de hoy
    pipeline = [
        {"$match": {"date": today_start.isoformat(), "is_trial": False}},
        {"$group": {"_id": None, "total": {"$sum": "$amount_charged"}}},
    ]
    result = await db.daily_subscriptions.aggregate(pipeline).to_list(1)
    revenue_today = result[0]["total"] if result else 0

    # Suscripciones del mes
    month_start = today_start.replace(day=1)
    monthly_pipeline = [
        {"$match": {"date": {"$gte": month_start.isoformat()}, "is_trial": False}},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": "$amount_charged"},
                "count": {"$sum": 1},
            }
        },
    ]
    monthly_result = await db.daily_subscriptions.aggregate(monthly_pipeline).to_list(1)

    # Usuarios en trial
    users_in_trial = await db.daily_subscriptions.count_documents(
        {"date": today_start.isoformat(), "is_trial": True}
    )

    return {
        "active_subscriptions_today": active_today,
        "revenue_today_usd": revenue_today,
        "revenue_month_usd": monthly_result[0]["total"] if monthly_result else 0,
        "subscriptions_month": monthly_result[0]["count"] if monthly_result else 0,
        "users_in_trial_today": users_in_trial,
        "daily_fee": await get_daily_fee(),
    }

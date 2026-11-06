"""
OMNI - Rutas de Suscripción Diaria
==================================
Endpoints para el sistema de suscripción de $1/día para socios.
"""

from fastapi import APIRouter, Depends, HTTPException
from utils.auth import get_current_user
from utils.subscription_system import (
    get_subscription_status,
    activate_subscription,
    deactivate_subscription,
    get_subscription_stats,
    get_daily_fee,
    get_free_trial_days,
)

router = APIRouter(prefix="/subscription", tags=["Subscription"])


@router.get("/status")
async def get_my_subscription_status(user: dict = Depends(get_current_user)):
    """
    Obtener el estado de suscripción del usuario actual.

    Retorna:
    - has_active_subscription: Si ya pagó hoy
    - in_free_trial: Si está en período de prueba
    - trial_days_remaining: Días de trial restantes
    - daily_fee: Costo diario ($1)
    - balance: Saldo actual en billetera
    - can_activate: Si puede activarse
    """
    user_id = user.get("user_id")
    status = await get_subscription_status(user_id)
    return status


@router.post("/activate")
async def activate_my_subscription(user: dict = Depends(get_current_user)):
    """
    Activar la suscripción diaria.

    - Si está en trial (3 días gratis): Se activa sin costo
    - Si ya pagó hoy: Se reactiva sin costo adicional
    - Si no: Se descuenta $1 de la billetera

    Retorna:
    - success: True/False
    - message: Mensaje descriptivo
    - charged: Monto cobrado
    - valid_until: Válido hasta (23:59:59)
    """
    user_id = user.get("user_id")
    user_name = user.get("name", "Usuario")

    result = await activate_subscription(user_id, user_name)

    if not result["success"]:
        raise HTTPException(status_code=402, detail=result)

    return result


@router.post("/deactivate")
async def deactivate_my_subscription(user: dict = Depends(get_current_user)):
    """
    Desactivar la suscripción (desconectarse).

    Nota: No hay reembolso. El usuario puede volver a activarse
    hasta medianoche sin costo adicional.
    """
    user_id = user.get("user_id")
    result = await deactivate_subscription(user_id)
    return result


@router.get("/info")
async def get_subscription_info():
    """
    Obtener información pública del sistema de suscripción.
    """
    return {
        "daily_fee": await get_daily_fee(),
        "free_trial_days": await get_free_trial_days(),
        "currency": "USD",
        "valid_until": "23:59:59 (medianoche)",
        "description": "Suscripción diaria para operar en la plataforma OMNI",
    }


@router.get("/admin/stats")
async def get_admin_subscription_stats(user: dict = Depends(get_current_user)):
    """
    Obtener estadísticas de suscripciones (solo admin).
    """
    if "admin" not in user.get("role", []):
        raise HTTPException(status_code=403, detail="Solo administradores")

    stats = await get_subscription_stats()
    return stats

"""
Rutas para Gestión de Pedidos del Socio Comercial

Implementa la funcionalidad para que los comercios puedan:
- Ver pedidos entrantes en tiempo real
- Aceptar pedidos (cambia a PREPARING)
- Rechazar pedidos (cancela y reembolsa si aplica)
- Marcar pedidos como listos para entrega
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
import uuid

from utils.database import db
from utils.auth import get_current_user

router = APIRouter(prefix="/comercial/orders", tags=["Comercial Orders"])


# Estados de pedido
ORDER_STATUS = {
    "pending": "Pendiente",  # Nuevo pedido
    "preparing": "Preparando",  # Comercio aceptó y prepara
    "ready": "Listo para entrega",  # Listo para el repartidor
    "picked_up": "Recogido",  # Repartidor recogió
    "delivering": "En camino",  # En delivery
    "completed": "Completado",  # Entregado
    "cancelled": "Cancelado",  # Rechazado/Cancelado
}


async def get_comercial_store(user_id: str):
    """Obtener la tienda del comercial"""
    # Buscar en store_profiles (nuevo sistema)
    store = await db.store_profiles.find_one({"user_id": user_id}, {"_id": 0})
    if store:
        return store

    # Fallback: buscar en socios_comerciales (legacy)
    legacy = await db.socios_comerciales.find_one({"user_id": user_id}, {"_id": 0})
    return legacy


@router.get("/incoming")
async def get_incoming_orders(user: dict = Depends(get_current_user)):
    """
    Obtener pedidos entrantes para el comercio.
    Solo muestra pedidos pending que aún no han sido aceptados.
    """
    if user["role"] != "socio_comercial" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    store = await get_comercial_store(user["user_id"])
    if not store:
        raise HTTPException(status_code=404, detail="No tienes un comercio registrado")

    store_id = store.get("store_id") or store.get("comercial_id")

    # Buscar pedidos pendientes
    orders = (
        await db.orders.find({"store_id": store_id, "status": "pending"}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )

    # Enriquecer con info del cliente
    for order in orders:
        customer = await db.users.find_one(
            {"user_id": order.get("user_id")}, {"_id": 0, "name": 1, "phone": 1}
        )
        order["customer_name"] = (
            customer.get("name", "Cliente") if customer else "Cliente"
        )
        order["customer_phone"] = customer.get("phone", "") if customer else ""

    return {"orders": orders, "count": len(orders)}


@router.get("/active")
async def get_active_orders(user: dict = Depends(get_current_user)):
    """
    Obtener pedidos activos (en preparación o listos).
    """
    if user["role"] != "socio_comercial" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    store = await get_comercial_store(user["user_id"])
    if not store:
        raise HTTPException(status_code=404, detail="No tienes un comercio registrado")

    store_id = store.get("store_id") or store.get("comercial_id")

    orders = (
        await db.orders.find(
            {
                "store_id": store_id,
                "status": {"$in": ["preparing", "ready", "picked_up", "delivering"]},
            },
            {"_id": 0},
        )
        .sort("created_at", -1)
        .to_list(50)
    )

    # Enriquecer con info
    for order in orders:
        customer = await db.users.find_one(
            {"user_id": order.get("user_id")}, {"_id": 0, "name": 1, "phone": 1}
        )
        order["customer_name"] = (
            customer.get("name", "Cliente") if customer else "Cliente"
        )

        if order.get("driver_id"):
            driver = await db.socios_repartidores.find_one(
                {"socio_id": order["driver_id"]}, {"_id": 0, "user_id": 1}
            )
            if driver:
                driver_user = await db.users.find_one(
                    {"user_id": driver["user_id"]}, {"_id": 0, "name": 1, "phone": 1}
                )
                order["driver_name"] = (
                    driver_user.get("name", "Repartidor")
                    if driver_user
                    else "Repartidor"
                )

    return {"orders": orders, "count": len(orders)}


@router.get("/history")
async def get_order_history(limit: int = 20, user: dict = Depends(get_current_user)):
    """
    Obtener historial de pedidos completados/cancelados.
    """
    if user["role"] != "socio_comercial" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    store = await get_comercial_store(user["user_id"])
    if not store:
        raise HTTPException(status_code=404, detail="No tienes un comercio registrado")

    store_id = store.get("store_id") or store.get("comercial_id")

    orders = (
        await db.orders.find(
            {"store_id": store_id, "status": {"$in": ["completed", "cancelled"]}},
            {"_id": 0},
        )
        .sort("created_at", -1)
        .to_list(limit)
    )

    return {"orders": orders}


@router.post("/{order_id}/accept")
async def accept_order(order_id: str, user: dict = Depends(get_current_user)):
    """
    Aceptar un pedido entrante.
    Cambia el estado a 'preparing' y notifica al cliente/repartidor.
    """
    if user["role"] != "socio_comercial" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    store = await get_comercial_store(user["user_id"])
    if not store:
        raise HTTPException(status_code=404, detail="No tienes un comercio registrado")

    store_id = store.get("store_id") or store.get("comercial_id")

    # Verificar que el pedido pertenece a este comercio
    order = await db.orders.find_one(
        {"order_id": order_id, "store_id": store_id}, {"_id": 0}
    )

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if order["status"] != "pending":
        raise HTTPException(
            status_code=400, detail=f"El pedido ya está en estado: {order['status']}"
        )

    # Actualizar estado
    now = datetime.now(timezone.utc).isoformat()
    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "status": "preparing",
                "accepted_at": now,
                "accepted_by": user["user_id"],
            }
        },
    )

    # TODO: Enviar notificación push al cliente
    # TODO: Buscar repartidor disponible

    return {
        "message": "Pedido aceptado. ¡Comienza a preparar!",
        "order_id": order_id,
        "new_status": "preparing",
    }


@router.post("/{order_id}/reject")
async def reject_order(
    order_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """
    Rechazar un pedido.
    Cancela el pedido y si el cliente pagó en wallet, se reembolsa.
    """
    if user["role"] != "socio_comercial" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    store = await get_comercial_store(user["user_id"])
    if not store:
        raise HTTPException(status_code=404, detail="No tienes un comercio registrado")

    store_id = store.get("store_id") or store.get("comercial_id")

    body = await request.json()
    reason = body.get("reason", "Rechazado por el comercio")

    order = await db.orders.find_one(
        {"order_id": order_id, "store_id": store_id}, {"_id": 0}
    )

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if order["status"] not in ["pending", "preparing"]:
        raise HTTPException(
            status_code=400, detail="Este pedido no puede ser rechazado"
        )

    now = datetime.now(timezone.utc).isoformat()

    # Actualizar estado
    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "status": "cancelled",
                "cancelled_at": now,
                "cancelled_by": user["user_id"],
                "cancel_reason": reason,
            }
        },
    )

    # Reembolsar si el cliente pagó con wallet
    refund_amount = 0
    if order.get("paid_with_wallet"):
        refund_amount = order.get("total_usd", 0)

        await db.users.update_one(
            {"user_id": order["user_id"]}, {"$inc": {"wallet_balance": refund_amount}}
        )

        # Registrar transacción de reembolso
        await db.transactions.insert_one(
            {
                "transaction_id": f"refund_{uuid.uuid4().hex[:12]}",
                "user_id": order["user_id"],
                "amount_usd": refund_amount,
                "type": "REFUND",
                "status": "completed",
                "reference": order_id,
                "description": f"Reembolso pedido #{order_id[-6:]} - {reason}",
                "created_at": now,
            }
        )

    return {
        "message": f"Pedido rechazado: {reason}",
        "order_id": order_id,
        "refunded": refund_amount > 0,
        "refund_amount": refund_amount,
    }


@router.post("/{order_id}/ready")
async def mark_order_ready(order_id: str, user: dict = Depends(get_current_user)):
    """
    Marcar pedido como listo para entrega.
    Notifica al repartidor que puede recoger.
    """
    if user["role"] != "socio_comercial" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    store = await get_comercial_store(user["user_id"])
    if not store:
        raise HTTPException(status_code=404, detail="No tienes un comercio registrado")

    store_id = store.get("store_id") or store.get("comercial_id")

    order = await db.orders.find_one(
        {"order_id": order_id, "store_id": store_id}, {"_id": 0}
    )

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if order["status"] != "preparing":
        raise HTTPException(
            status_code=400, detail="Solo pedidos en preparación pueden marcarse listos"
        )

    now = datetime.now(timezone.utc).isoformat()

    await db.orders.update_one(
        {"order_id": order_id}, {"$set": {"status": "ready", "ready_at": now}}
    )

    # TODO: Notificar al repartidor

    return {
        "message": "¡Pedido listo! Esperando al repartidor.",
        "order_id": order_id,
        "new_status": "ready",
    }


@router.get("/stats/today")
async def get_today_stats(user: dict = Depends(get_current_user)):
    """
    Obtener estadísticas del día para el comercio.
    """
    if user["role"] != "socio_comercial" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    store = await get_comercial_store(user["user_id"])
    if not store:
        raise HTTPException(status_code=404, detail="No tienes un comercio registrado")

    store_id = store.get("store_id") or store.get("comercial_id")

    # Obtener fecha de hoy
    today_start = (
        datetime.now(timezone.utc)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
    )

    # Contar pedidos de hoy
    pipeline = [
        {"$match": {"store_id": store_id, "created_at": {"$gte": today_start}}},
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total": {"$sum": "$total_usd"},
            }
        },
    ]

    results = await db.orders.aggregate(pipeline).to_list(10)

    stats = {
        "pending": 0,
        "preparing": 0,
        "completed": 0,
        "cancelled": 0,
        "total_orders": 0,
        "total_revenue": 0.0,
    }

    for r in results:
        status = r["_id"]
        if status in stats:
            stats[status] = r["count"]
        stats["total_orders"] += r["count"]
        if status == "completed":
            stats["total_revenue"] += r.get("total", 0)

    return stats

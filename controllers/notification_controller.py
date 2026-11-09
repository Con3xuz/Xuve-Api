"""Controlador de notification - Validaciones y lógica de negocio."""
from models import *
"""
Notification Routes - Sistema de notificaciones para Xuve SuperApp
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
import uuid

from models import db
from utils.auth import get_current_user



async def get_notifications(user: dict = Depends(get_current_user)):
    """Obtener notificaciones del usuario"""
    user_id = user.get("user_id")

    # Buscar por user_id directo y también por store_id si es comercio
    query = {"user_id": user_id}

    if user.get("role") == "socio_comercial":
        store = await StoreProfileModel.find_one(
            {"user_id": user_id}, {"_id": 0, "store_id": 1}
        )
        if store:
            query = {"$or": [{"user_id": user_id}, {"store_id": store["store_id"]}]}

    notifications = (
        await NotificationModel.find(query, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )

    unread_count = len([n for n in notifications if not n.get("read")])

    return {"notifications": notifications, "unread_count": unread_count}


async def mark_as_read(notification_id: str, user: dict = Depends(get_current_user)):
    """Marcar notificación como leída"""
    user_id = user.get("user_id")

    result = await NotificationModel.update_one(
        {"notification_id": notification_id, "user_id": user_id},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    return {"message": "Notificación marcada como leída"}


async def mark_all_as_read(user: dict = Depends(get_current_user)):
    """Marcar todas las notificaciones como leídas"""
    user_id = user.get("user_id")
    now = datetime.now(timezone.utc).isoformat()

    query = {"user_id": user_id, "read": False}

    if user.get("role") == "socio_comercial":
        store = await StoreProfileModel.find_one(
            {"user_id": user_id}, {"_id": 0, "store_id": 1}
        )
        if store:
            query = {
                "$or": [{"user_id": user_id}, {"store_id": store["store_id"]}],
                "read": False,
            }

    result = await NotificationModel.update_many(
        query, {"$set": {"read": True, "read_at": now}}
    )

    return {"message": f"{result.modified_count} notificaciones marcadas como leídas"}


async def delete_notification(
    notification_id: str, user: dict = Depends(get_current_user)
):
    """Eliminar notificación"""
    user_id = user.get("user_id")

    query = {"notification_id": notification_id, "user_id": user_id}

    if user.get("role") == "socio_comercial":
        store = await StoreProfileModel.find_one(
            {"user_id": user_id}, {"_id": 0, "store_id": 1}
        )
        if store:
            query = {
                "notification_id": notification_id,
                "$or": [{"user_id": user_id}, {"store_id": store["store_id"]}],
            }

    result = await NotificationModel.delete_one(query)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    return {"message": "Notificación eliminada"}


# ==================== HELPERS DE NOTIFICACIÓN ====================


async def send_notification(
    user_id: str,
    notif_type: str,
    title: str,
    message: str,
    data: dict = None,
    store_id: str = None,
):
    """Enviar notificación genérica a un usuario o tienda"""
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "store_id": store_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "data": data or {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await NotificationModel.insert_one(notification)
    notification.pop("_id", None)
    return notification


# ==================== NOTIFICACIONES DE KYC ====================


async def send_kyc_notification(
    user_id: str, status: str, role: str = None, reason: str = None
):
    """Enviar notificación de estado de KYC"""
    if status == "approved":
        message = f"¡Felicitaciones! Tu solicitud KYC ha sido aprobada. Ya eres {role}."
        notif_type = "kyc_approved"
    elif status == "rejected":
        message = f"Tu solicitud KYC ha sido rechazada. Razón: {reason}"
        notif_type = "kyc_rejected"
    elif status == "pending":
        message = "Tu solicitud KYC ha sido recibida y está en revisión."
        notif_type = "kyc_pending"
    else:
        message = f"Estado de KYC actualizado: {status}"
        notif_type = "kyc_update"

    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "type": notif_type,
        "message": message,
        "data": {"status": status, "role": role, "reason": reason},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await NotificationModel.insert_one(notification)
    return notification

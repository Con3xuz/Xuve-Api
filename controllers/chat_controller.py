"""Controlador de chat - Validaciones y lógica de negocio."""
from models import *
"""
Chat Routes - Sistema de mensajería operativa para Xuve SuperApp
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
import uuid

from models import db
from utils.auth import get_current_user



async def get_conversations(user: dict = Depends(get_current_user)):
    """Obtener todas las conversaciones del usuario"""
    user_id = user.get("user_id")

    conversations = (
        await ChatConversationModel.find({"participants": user_id}, {"_id": 0})
        .sort("updated_at", -1)
        .to_list(50)
    )

    # Contar mensajes no leídos
    for conv in conversations:
        unread = await ChatMessageModel.count_documents(
            {
                "conversation_id": conv["conversation_id"],
                "sender_id": {"$ne": user_id},
                "read": False,
            }
        )
        conv["unread_count"] = unread

    return {"conversations": conversations}


async def create_conversation(request: Request, user: dict = Depends(get_current_user)):
    """Crear nueva conversación"""
    body = await request.json()
    user_id = user.get("user_id")

    conv_type = body.get("type", "support")
    initial_message = body.get("initial_message")
    target_user_id = body.get("target_user_id")

    now = datetime.now(timezone.utc).isoformat()
    conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

    # Determinar participantes
    participants = [user_id]
    if target_user_id:
        participants.append(target_user_id)
    elif conv_type == "support":
        # Agregar cuenta de soporte genérica
        participants.append("support_xuve")

    conversation = {
        "conversation_id": conversation_id,
        "type": conv_type,
        "participants": participants,
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
        "status": "active",
    }

    await ChatConversationModel.insert_one(conversation)

    # Remove _id before returning
    conversation.pop("_id", None)

    result = {"conversation": conversation}

    # Si hay mensaje inicial, agregarlo
    if initial_message:
        message = await create_message_internal(
            conversation_id, user_id, user.get("name"), initial_message
        )
        result["message"] = message

    return result


async def get_messages(conversation_id: str, user: dict = Depends(get_current_user)):
    """Obtener mensajes de una conversación"""
    user_id = user.get("user_id")

    # Verificar que el usuario es participante
    conv = await ChatConversationModel.find_one(
        {"conversation_id": conversation_id, "participants": user_id}
    )

    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    messages = (
        await ChatMessageModel.find({"conversation_id": conversation_id}, {"_id": 0})
        .sort("created_at", 1)
        .to_list(100)
    )

    # Marcar como leídos los mensajes de otros usuarios
    await ChatMessageModel.update_many(
        {
            "conversation_id": conversation_id,
            "sender_id": {"$ne": user_id},
            "read": False,
        },
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
    )

    return {"messages": messages}


async def send_message(
    conversation_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """Enviar mensaje a una conversación"""
    body = await request.json()
    user_id = user.get("user_id")
    content = body.get("content")

    if not content:
        raise HTTPException(status_code=400, detail="Contenido requerido")

    # Verificar participación
    conv = await ChatConversationModel.find_one(
        {"conversation_id": conversation_id, "participants": user_id}
    )

    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    message = await create_message_internal(
        conversation_id, user_id, user.get("name"), content
    )

    # Actualizar timestamp de conversación
    await ChatConversationModel.update_one(
        {"conversation_id": conversation_id},
        {"$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Crear notificación para otros participantes
    for participant_id in conv["participants"]:
        if participant_id != user_id and participant_id != "support_xuve":
            await create_notification_internal(
                participant_id,
                "chat_message",
                f"Nuevo mensaje de {user.get('name')}",
                {
                    "conversation_id": conversation_id,
                    "message_id": message["message_id"],
                },
            )

    return {"message": message}


# ==================== SERVICE CHAT (Uber/Glovo style) ====================


async def get_service_conversation(
    service_type: str, service_id: str, user: dict = Depends(get_current_user)
):
    """
    Obtener conversación de un servicio activo (viaje, entrega, alquiler)
    """
    user_id = user.get("user_id")

    # Buscar conversación existente para este servicio
    conversation = await ChatConversationModel.find_one(
        {
            "service_type": service_type,
            "service_id": service_id,
            "participants": user_id,
        },
        {"_id": 0},
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    # Obtener mensajes
    messages = (
        await ChatMessageModel.find(
            {"conversation_id": conversation["conversation_id"]}, {"_id": 0}
        )
        .sort("created_at", 1)
        .to_list(100)
    )

    return {"conversation_id": conversation["conversation_id"], "messages": messages}


async def create_service_conversation(
    request: Request, user: dict = Depends(get_current_user)
):
    """
    Crear conversación para un servicio activo
    """
    body = await request.json()
    service_type = body.get("service_type")  # ride, delivery, rent
    service_id = body.get("service_id")
    other_user_id = body.get("other_user_id")

    if not all([service_type, service_id, other_user_id]):
        raise HTTPException(status_code=400, detail="Faltan datos requeridos")

    user_id = user.get("user_id")
    user_name = user.get("name", "Usuario")

    # Verificar si ya existe
    existing = await ChatConversationModel.find_one(
        {"service_type": service_type, "service_id": service_id}
    )

    if existing:
        existing.pop("_id", None)
        return {"conversation_id": existing["conversation_id"], "existing": True}

    # Obtener info del otro usuario
    other_user = await UserModel.find_one(
        {"user_id": other_user_id}, {"_id": 0, "name": 1}
    )
    other_name = other_user.get("name", "Usuario") if other_user else "Usuario"

    conversation_id = f"svc_{service_type}_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    conversation = {
        "conversation_id": conversation_id,
        "type": f"service_{service_type}",
        "service_type": service_type,
        "service_id": service_id,
        "participants": [user_id, other_user_id],
        "participant_names": {user_id: user_name, other_user_id: other_name},
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
        "status": "active",
    }

    await ChatConversationModel.insert_one(conversation)
    conversation.pop("_id", None)

    return {"conversation_id": conversation_id, "conversation": conversation}


async def create_message_internal(
    conversation_id: str, sender_id: str, sender_name: str, content: str
):
    """Helper para crear mensajes"""
    message = {
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "conversation_id": conversation_id,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "content": content,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await ChatMessageModel.insert_one(message)
    # Remove _id before returning
    message.pop("_id", None)
    return message


async def create_notification_internal(
    user_id: str, notif_type: str, message: str, data: dict = None
):
    """Helper para crear notificaciones"""
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "type": notif_type,
        "message": message,
        "data": data or {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await NotificationModel.insert_one(notification)
    # Remove _id before returning
    notification.pop("_id", None)
    return notification

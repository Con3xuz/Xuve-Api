"""
Modelos SQL de Conversaciones, Mensajes de Chat, Notificaciones y Rutas Fijas (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from models.base import PostgresBaseModel


class ChatConversationModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.chat_conversations`."""
    _table_name = "chat_conversations"

    @classmethod
    async def find_by_id(cls, conversation_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.chat_conversations WHERE doc->>'conversation_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, conversation_id)


class ChatMessageModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.chat_messages`."""
    _table_name = "chat_messages"

    @classmethod
    async def list_by_conversation_id(cls, conversation_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.chat_messages WHERE doc->>'conversation_id' = $1 ORDER BY created_at ASC LIMIT $2"
        return await cls.sql_fetch_all(sql, conversation_id, limit)


class NotificationModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.notifications`."""
    _table_name = "notifications"

    @classmethod
    async def list_by_user_id(cls, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.notifications WHERE doc->>'user_id' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, user_id, limit)


class FixedRouteModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.fixed_routes`."""
    _table_name = "fixed_routes"

    @classmethod
    async def find_by_id(cls, route_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.fixed_routes WHERE doc->>'route_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, route_id)


ChatMessage = ChatMessageModel
FixedRoute = FixedRouteModel

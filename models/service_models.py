"""
Modelos SQL de Servicios de Movilidad, Calificaciones y Disponibilidad (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from enum import Enum
from models.base import PostgresBaseModel


class ServiceType(str, Enum):
    RIDE = "ride"
    DELIVERY = "delivery"
    GENERAL = "general"


class ServiceStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ServiceModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.services`."""
    _table_name = "services"

    @classmethod
    async def find_by_id(cls, service_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.services WHERE doc->>'service_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, service_id)

    @classmethod
    async def list_by_user_id(cls, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.services WHERE doc->>'user_id' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, user_id, limit)

    @classmethod
    async def list_by_status(cls, status: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.services WHERE doc->>'status' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, status, limit)


class RatingModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.ratings`."""
    _table_name = "ratings"

    @classmethod
    async def list_by_target(cls, target_user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.ratings WHERE doc->>'target_id' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, target_user_id, limit)


class ProviderAvailabilityModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.provider_availability`."""
    _table_name = "provider_availability"

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.provider_availability WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)


class ServiceMessageModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.messages`."""
    _table_name = "messages"

    @classmethod
    async def list_by_service_id(cls, service_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.messages WHERE doc->>'service_id' = $1 ORDER BY created_at ASC LIMIT $2"
        return await cls.sql_fetch_all(sql, service_id, limit)


Service = ServiceModel

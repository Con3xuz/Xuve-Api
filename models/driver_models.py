"""
Modelos SQL de Conductores y Flota (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from models.base import PostgresBaseModel


class DriverModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.drivers`."""
    _table_name = "drivers"

    @classmethod
    async def find_by_id(cls, driver_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.drivers WHERE doc->>'driver_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, driver_id)

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.drivers WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)

    @classmethod
    async def list_by_status(cls, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.drivers WHERE doc->>'status' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, status, limit)


Driver = DriverModel

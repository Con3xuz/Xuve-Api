"""
Modelos SQL de Perfiles de Tienda y Categorías Comerciales (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from models.base import PostgresBaseModel
class StoreProfileModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.store_profiles`."""
    _table_name = "store_profiles"

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.store_profiles WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)

    @classmethod
    async def find_by_store_id(cls, store_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.store_profiles WHERE doc->>'store_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, store_id)


StoreProfile = StoreProfileModel

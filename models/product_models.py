"""
Modelos SQL de Catálogo de Productos para Comercios (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from enum import Enum
from models.base import PostgresBaseModel


class ProductStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    OUT_OF_STOCK = "out_of_stock"
    DELETED = "deleted"


class ProductModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.products`."""
    _table_name = "products"

    @classmethod
    async def find_by_id(cls, product_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.products WHERE doc->>'product_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, product_id)

    @classmethod
    async def list_by_store_id(cls, store_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.products WHERE doc->>'store_id' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, store_id, limit)

    @classmethod
    async def delete_by_id(cls, product_id: str) -> str:
        sql = "DELETE FROM xuve.products WHERE doc->>'product_id' = $1"
        return await cls.sql_execute(sql, product_id)

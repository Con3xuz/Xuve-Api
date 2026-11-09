"""
Modelos SQL de Market (Tiendas, Productos de Market y Órdenes) en PostgreSQL (Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from models.base import PostgresBaseModel


class MarketStoreModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.market_stores`."""
    _table_name = "market_stores"

    @classmethod
    async def find_by_id(cls, store_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.market_stores WHERE doc->>'store_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, store_id)

    @classmethod
    async def list_active(cls, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.market_stores WHERE (doc->>'is_active')::boolean = true LIMIT $1"
        return await cls.sql_fetch_all(sql, limit)


class MarketProductModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.market_products`."""
    _table_name = "market_products"

    @classmethod
    async def find_by_id(cls, product_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.market_products WHERE doc->>'product_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, product_id)

    @classmethod
    async def list_by_store_id(cls, store_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.market_products WHERE doc->>'store_id' = $1 LIMIT $2"
        return await cls.sql_fetch_all(sql, store_id, limit)


class MarketOrderModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.market_orders`."""
    _table_name = "market_orders"

    @classmethod
    async def find_by_id(cls, order_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.market_orders WHERE doc->>'order_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, order_id)


class OrderModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.orders`."""
    _table_name = "orders"

    @classmethod
    async def find_by_id(cls, order_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.orders WHERE doc->>'order_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, order_id)

    @classmethod
    async def list_by_user_id(cls, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.orders WHERE doc->>'user_id' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, user_id, limit)

    @classmethod
    async def list_by_store_id(cls, store_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.orders WHERE doc->>'store_id' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, store_id, limit)


MarketStore = MarketStoreModel
MarketProduct = MarketProductModel
Order = OrderModel

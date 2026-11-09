"""
Modelos SQL de catálogos y configuración de plataforma (PostgreSQL - esquema `xuve`).

Tablas relacionales (no documentales) que antes vivían "quemadas" en el código:
  - xuve.business_categories
  - xuve.product_categories
  - xuve.platform_settings
  - xuve.cargo_rates
"""

from typing import Any, Dict, List, Optional

from models.base import PostgresBaseModel, get_pool


class BusinessCategoryModel(PostgresBaseModel):
    """Modelo SQL para `xuve.business_categories`."""

    _table_name = "business_categories"

    @classmethod
    async def list_active(cls) -> List[Dict[str, Any]]:
        sql = (
            "SELECT slug, label, icon, color, emoji FROM xuve.business_categories "
            "WHERE active ORDER BY sort_order, label"
        )
        return await cls.sql_fetch_all(sql)

    @classmethod
    async def find_by_slug(cls, slug: str) -> Optional[Dict[str, Any]]:
        sql = (
            "SELECT slug, label, icon, color, emoji FROM xuve.business_categories "
            "WHERE slug = $1 AND active"
        )
        return await cls.sql_fetch_one(sql, slug)


class ProductCategoryModel(PostgresBaseModel):
    """Modelo SQL para `xuve.product_categories`."""

    _table_name = "product_categories"

    @classmethod
    async def list_by_store_type(cls, store_type: str) -> List[Dict[str, Any]]:
        sql = (
            "SELECT name, icon, subcategories FROM xuve.product_categories "
            "WHERE store_type = $1 AND active ORDER BY sort_order, name"
        )
        return await cls.sql_fetch_all(sql, store_type)


class PlatformSettingModel(PostgresBaseModel):
    """Modelo SQL para `xuve.platform_settings` (clave -> valor JSONB)."""

    _table_name = "platform_settings"

    @classmethod
    async def get_value(cls, key: str, default: Any = None) -> Any:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM xuve.platform_settings WHERE key = $1", key
            )
        return row["value"] if row else default

    @classmethod
    async def get_all(cls) -> Dict[str, Any]:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM xuve.platform_settings")
        return {r["key"]: r["value"] for r in rows}

    @classmethod
    async def upsert_many(cls, values: Dict[str, Any], updated_by: Optional[str] = None) -> None:
        sql = (
            "INSERT INTO xuve.platform_settings (key, value, updated_by) VALUES ($1, $2, $3) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, "
            "updated_by = EXCLUDED.updated_by, updated_at = now()"
        )
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                for key, value in values.items():
                    await conn.execute(sql, key, value, updated_by)


class CargoRateModel(PostgresBaseModel):
    """Modelo SQL para `xuve.cargo_rates`."""

    _table_name = "cargo_rates"

    @classmethod
    async def list_by_service(cls, service_type: str) -> List[Dict[str, Any]]:
        sql = (
            "SELECT tier, amount_usd FROM xuve.cargo_rates "
            "WHERE service_type = $1 AND active"
        )
        return await cls.sql_fetch_all(sql, service_type)

    @classmethod
    async def get_amount(cls, service_type: str, tier: str) -> Optional[float]:
        sql = (
            "SELECT amount_usd FROM xuve.cargo_rates "
            "WHERE service_type = $1 AND tier = $2 AND active"
        )
        pool = get_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval(sql, service_type, tier)
        return float(val) if val is not None else None


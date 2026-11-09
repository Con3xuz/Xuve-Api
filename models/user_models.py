"""
Modelos SQL de Usuarios, Sesiones, Autenticación y Socios (PostgreSQL - Esquema `xuve`).
Contiene las consultas SQL directas para la capa de persistencia de usuarios.
"""

from typing import Any, Dict, List, Optional
from models.base import PostgresBaseModel, get_pool

# ===========================================================================
# CONSTANTES DE DOMINIO (ROLES Y CATEGORÍAS DE VEHÍCULOS)
# ===========================================================================

VALID_ROLES = [
    "user",
    "socio_conductor",
    "socio_repartidor",
    "socio_comercial",
    "rent_owner",
    "carga_pesada",
    "line_admin",
    "chofer_linea",
    "transporte_interurbano",
    "urban_line_admin",
    "chofer_urbano",
    "medico",
    "admin",
]

KYC_ELEVATABLE_ROLES = {r for r in VALID_ROLES if r not in ("admin", "user")}

CONDUCTOR_VEHICLE_TYPES = ["carro_particular", "taxi_linea", "mototaxi"]
REPARTIDOR_VEHICLE_TYPES = ["bicicleta", "monopatín_electrico", "moto_delivery"]
CARGA_VEHICLE_TYPES = ["camion_350", "camion_750", "camion_cava", "cisterna"]
LINE_VEHICLE_TYPES = ["buseta", "van", "expreso", "minibus", "autobus"]
LINE_SERVICE_TYPES = ["interurbano", "urbano"]

SELF_REGISTRABLE_ROLE = "user"
PRIVILEGED_ROLES = {"admin"}


# ===========================================================================
# MODELOS SQL DE BASE DE DATOS (TABLAS EN ESQUEMA `xuve`)
# ===========================================================================


class UserModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.users`."""

    _table_name = "users"

    @classmethod
    async def find_by_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.users WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)

    @classmethod
    async def find_by_email(cls, email: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.users WHERE doc->>'email' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, email)

    @classmethod
    async def create_user(cls, user_doc: Dict[str, Any]) -> int:
        sql = "INSERT INTO xuve.users (doc) VALUES ($1) RETURNING pk"
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(sql, user_doc)

    @classmethod
    async def update_by_id(cls, user_id: str, fields: Dict[str, Any]):
        return await cls.update_one({"user_id": user_id}, {"$set": fields})

    @classmethod
    async def delete_by_id(cls, user_id: str) -> str:
        sql = "DELETE FROM xuve.users WHERE doc->>'user_id' = $1"
        return await cls.sql_execute(sql, user_id)

    @classmethod
    async def list_by_role(cls, role: str, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.users WHERE doc->>'role' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, role, limit)


class UserSessionModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.user_sessions`."""

    _table_name = "user_sessions"

    @classmethod
    async def find_by_token(cls, session_token: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.user_sessions WHERE doc->>'session_token' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, session_token)

    @classmethod
    async def delete_by_token(cls, session_token: str) -> str:
        sql = "DELETE FROM xuve.user_sessions WHERE doc->>'session_token' = $1"
        return await cls.sql_execute(sql, session_token)


class EmailVerificationModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.email_verifications`."""

    _table_name = "email_verifications"

    @classmethod
    async def find_by_email(cls, email: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.email_verifications WHERE doc->>'email' = $1 ORDER BY created_at DESC LIMIT 1"
        return await cls.sql_fetch_one(sql, email)

    @classmethod
    async def delete_by_email(cls, email: str) -> str:
        sql = "DELETE FROM xuve.email_verifications WHERE doc->>'email' = $1"
        return await cls.sql_execute(sql, email)


class PasswordResetModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.password_resets`."""

    _table_name = "password_resets"

    @classmethod
    async def find_by_token(cls, token: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.password_resets WHERE doc->>'token' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, token)

    @classmethod
    async def delete_by_email(cls, email: str) -> str:
        sql = "DELETE FROM xuve.password_resets WHERE doc->>'email' = $1"
        return await cls.sql_execute(sql, email)


class SocioConductorModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.socios_conductores`."""

    _table_name = "socios_conductores"

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.socios_conductores WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)


class SocioRepartidorModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.socios_repartidores`."""

    _table_name = "socios_repartidores"

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.socios_repartidores WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)


class SocioComercialModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.socios_comerciales`."""

    _table_name = "socios_comerciales"

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.socios_comerciales WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)


class SocioCargaPesadaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.socios_carga_pesada`."""

    _table_name = "socios_carga_pesada"

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.socios_carga_pesada WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)


class SocioInterurbanoModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.socios_interurbano`."""

    _table_name = "socios_interurbano"

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.socios_interurbano WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)


class PlatformConfigModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.platform_config`."""

    _table_name = "platform_config"

    @classmethod
    async def get_config(cls, config_id: str = "financial_config") -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.platform_config WHERE doc->>'config_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, config_id)


class DailySubscriptionModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.daily_subscriptions`."""

    _table_name = "daily_subscriptions"

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.daily_subscriptions WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)


class SubscriptionHistoryModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.subscription_history`."""

    _table_name = "subscription_history"

    @classmethod
    async def list_by_user_id(cls, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.subscription_history WHERE doc->>'user_id' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, user_id, limit)


class SubscriptionPaymentModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.subscription_payments`."""

    _table_name = "subscription_payments"

    @classmethod
    async def find_by_reference(cls, reference: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.subscription_payments WHERE doc->>'reference' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, reference)


# Alias de compatibilidad
User = UserModel

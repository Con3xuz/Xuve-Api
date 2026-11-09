"""
Modelos SQL de Líneas de Transporte Urbano B2B (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from enum import Enum
from models.base import PostgresBaseModel


class UrbanLineStatus(str, Enum):
    PENDING_KYC = "pending_kyc"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class LineaUrbanaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.lineas_urbanas`."""
    _table_name = "lineas_urbanas"

    @classmethod
    async def find_by_id(cls, linea_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.lineas_urbanas WHERE doc->>'linea_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, linea_id)

    @classmethod
    async def find_by_admin_user_id(cls, admin_user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.lineas_urbanas WHERE doc->>'admin_user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, admin_user_id)


class VehiculoUrbanoModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.vehiculos_urbanos`."""
    _table_name = "vehiculos_urbanos"


class ChoferUrbanoModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.choferes_urbanos`."""
    _table_name = "choferes_urbanos"


class RecorridoUrbanoModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.recorridos_urbanos`."""
    _table_name = "recorridos_urbanos"


class RecorridoUrbanoHistoricoModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.recorridos_urbanos_historico`."""
    _table_name = "recorridos_urbanos_historico"


class AsignacionUrbanaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.asignaciones_urbanas`."""
    _table_name = "asignaciones_urbanas"

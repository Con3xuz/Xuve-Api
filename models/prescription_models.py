"""
Modelos SQL de Médicos y Recetas Médicas Digitales (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from models.base import PostgresBaseModel


class MedicoModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.medicos`."""
    _table_name = "medicos"

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.medicos WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)


class PrescriptionModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.prescriptions`."""
    _table_name = "prescriptions"

    @classmethod
    async def find_by_id(cls, prescription_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.prescriptions WHERE doc->>'prescription_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, prescription_id)

    @classmethod
    async def list_by_patient_id(cls, patient_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.prescriptions WHERE doc->>'user_id' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, patient_id, limit)

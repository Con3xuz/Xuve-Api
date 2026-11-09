"""
Modelos SQL de Verificación de Identidad KYC (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from models.base import PostgresBaseModel
"""
KYC Models - Sistema de Verificación Modular para Xuve SuperApp

Este módulo define los esquemas polimórficos de KYC para cada tipo de socio:
- Conductor / Repartidor: Vehículos ligeros
- Carga Pesada / Chofer Interurbano / Chofer Urbano: Vehículos pesados (5ta)
- Terminal Admin / Línea Urbana: Corporativo B2B
- Comercial: Tiendas y comercios
- Rent Owner: Propietarios de vehículos para alquiler
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum

# ==================== ENUMS Y CONSTANTES ====================


class KYCStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    INCOMPLETE = "incomplete"


class LicenseGrade(str, Enum):
    SEGUNDA = "2da"
    TERCERA = "3ra"
    CUARTA = "4ta"
    QUINTA = "5ta"


# Roles que pueden solicitar KYC
KYC_ROLE_TYPES = [
    "socio_conductor",  # Taxi/Carro particular
    "socio_repartidor",  # Moto delivery / Bicicleta
    "carga_pesada",  # Camionero
    "chofer_linea",  # Chofer interurbano
    "chofer_urbano",  # Chofer de buseta urbana
    "line_admin",  # Admin Terminal B2B
    "urban_line_admin",  # Admin Línea Urbana B2B
    "socio_comercial",  # Comerciante
    "rent_owner",  # Propietario Rent-a-Car
]

# Categorías de vehículos
VEHICLE_CATEGORIES = {
    "ligero": [
        "carro_particular",
        "taxi_linea",
        "mototaxi",
        "moto_delivery",
        "bicicleta",
    ],
    "pesado": [
        "camion_350",
        "camion_750",
        "camion_cava",
        "cisterna",
        "buseta",
        "van",
        "expreso",
        "autobus",
    ],
}


# ==================== SUB-ESQUEMAS OPCIONALES ====================




class KYCRequestModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.kyc_requests`."""
    _table_name = "kyc_requests"

    @classmethod
    async def find_by_id(cls, kyc_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.kyc_requests WHERE doc->>'kyc_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, kyc_id)

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.kyc_requests WHERE doc->>'user_id' = $1 ORDER BY created_at DESC LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)

    @classmethod
    async def list_by_status(cls, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.kyc_requests WHERE doc->>'status' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, status, limit)


KYCRequest = KYCRequestModel

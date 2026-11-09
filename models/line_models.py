"""
Modelos SQL de Líneas de Transporte Interurbano, Carga Pesada y Rutas (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from enum import Enum
from models.base import PostgresBaseModel


class LineServiceType(str, Enum):
    INTERURBANO = "interurbano"
    URBANO = "urbano"


class LineStatus(str, Enum):
    PENDING_KYC = "pending_kyc"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class VehicleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    PENDING = "pending"
    APPROVED = "approved"
    SUSPENDED = "suspended"


class ChoferStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    APPROVED = "approved"
    ASSIGNED = "assigned"
    SUSPENDED = "suspended"


class LineaTransporteModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.lineas_transporte`."""
    _table_name = "lineas_transporte"

    @classmethod
    async def find_by_id(cls, linea_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.lineas_transporte WHERE doc->>'linea_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, linea_id)

    @classmethod
    async def find_by_admin_user_id(cls, admin_user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.lineas_transporte WHERE doc->>'admin_user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, admin_user_id)


class VehiculoLineaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.vehiculos_linea`."""
    _table_name = "vehiculos_linea"

    @classmethod
    async def find_by_id(cls, vehiculo_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.vehiculos_linea WHERE doc->>'vehiculo_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, vehiculo_id)

    @classmethod
    async def list_by_linea_id(cls, linea_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.vehiculos_linea WHERE doc->>'linea_id' = $1 LIMIT $2"
        return await cls.sql_fetch_all(sql, linea_id, limit)


class ChoferLineaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.choferes_linea`."""
    _table_name = "choferes_linea"

    @classmethod
    async def find_by_id(cls, chofer_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.choferes_linea WHERE doc->>'chofer_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, chofer_id)


class ViajeInterurbanoModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.viajes_interurbano`."""
    _table_name = "viajes_interurbano"

    @classmethod
    async def find_by_id(cls, viaje_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.viajes_interurbano WHERE doc->>'viaje_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, viaje_id)


class ReservaInterurbanoModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.reservas_interurbano`."""
    _table_name = "reservas_interurbano"


class ViajeModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.viajes`."""
    _table_name = "viajes"


class RutaUrbanaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.rutas_urbanas`."""
    _table_name = "rutas_urbanas"


class RutaUrbanaV2Model(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.rutas_urbanas_v2`."""
    _table_name = "rutas_urbanas_v2"


class RecorridoActivoModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.recorridos_activos`."""
    _table_name = "recorridos_activos"


class RecorridoHistoricoModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.recorridos_historico`."""
    _table_name = "recorridos_historico"


class AsignacionRutaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.asignaciones_ruta`."""
    _table_name = "asignaciones_ruta"


class MicropagoUrbanoModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.micropagos_urbanos`."""
    _table_name = "micropagos_urbanos"


class MicropagoQRModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.micropagos_qr`."""
    _table_name = "micropagos_qr"


class RutaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.rutas`."""
    _table_name = "rutas"


class CotizacionCargaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.cotizaciones_carga`."""
    _table_name = "cotizaciones_carga"


class VehiculoCargaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.vehiculos_carga`."""
    _table_name = "vehiculos_carga"


class ServicioCargaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.servicios_carga`."""
    _table_name = "servicios_carga"


class OperadorCargaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.operadores_carga`."""
    _table_name = "operadores_carga"


class NotificacionCargaModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.notificaciones_carga`."""
    _table_name = "notificaciones_carga"


LineaTransporte = LineaTransporteModel
VehiculoLinea = VehiculoLineaModel
ChoferLinea = ChoferLineaModel
ViajeInterurbano = ViajeInterurbanoModel
RutaUrbana = RutaUrbanaModel
ReservaInterurbano = ReservaInterurbanoModel
MicropagoQR = MicropagoQRModel
RecorridoActivo = RecorridoActivoModel

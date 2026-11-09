"""
Modelos SQL de Alquiler de Vehículos P2P — Xuve Rent (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from models.base import PostgresBaseModel


class RentCarModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.rent_cars`."""
    _table_name = "rent_cars"

    @classmethod
    async def find_by_id(cls, car_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.rent_cars WHERE doc->>'car_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, car_id)


class RentRequestModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.rent_requests`."""
    _table_name = "rent_requests"


class RentOwnerModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.rent_owners`."""
    _table_name = "rent_owners"


class RentVehicleModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.rent_vehicles`."""
    _table_name = "rent_vehicles"


class RentalModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.rentals`."""
    _table_name = "rentals"

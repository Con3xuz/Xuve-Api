"""
Capa de acceso a datos de Xuve sobre PostgreSQL (asyncpg).
Gestiona el pool de conexiones y el esquema documental relacional.
"""

import logging

from models.base import Database, db
from db.pg import init_pool as _init_pool, close_pool as _close_pool
from db.schema import bootstrap_schema as _bootstrap_schema

logger = logging.getLogger(__name__)


def get_db() -> Database:
    return db


async def init_db() -> None:
    """Inicializa el pool de PostgreSQL y crea el esquema (idempotente).

    Debe llamarse en el evento `startup` de FastAPI.
    """
    await _init_pool()
    await _bootstrap_schema()
    logger.info("Base de datos PostgreSQL lista")


async def close_db() -> None:
    """Cierra el pool de conexiones. Se llama en el `shutdown` de FastAPI."""
    await _close_pool()

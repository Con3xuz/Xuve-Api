"""
Capa de acceso a datos de Xuve.

Migrado de MongoDB (motor) a PostgreSQL (asyncpg) mediante la capa de
compatibilidad `db.mongo_compat`. La interfaz pública (`db`, `get_db`,
`close_db`) se mantiene idéntica para no tocar los ~675 call sites.
"""

import logging

from db.mongo_compat import Database
from db.pg import init_pool as _init_pool, close_pool as _close_pool
from db.schema import bootstrap_schema as _bootstrap_schema

logger = logging.getLogger(__name__)

# Objeto compatible con la API de MongoDB usado en todo el backend: db.<col>.<op>()
db = Database()


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

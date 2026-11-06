"""
PostgreSQL connection pool (asyncpg).

Reemplaza la conexión de MongoDB (motor). Expone un pool global de asyncpg
configurado de forma agresiva para soportar picos de miles de usuarios
concurrentes, y un codec JSONB <-> Python para que las filas `doc` se
serialicen/deserialicen automáticamente como dict/list/escalares.

NO usa ORM: el adaptador de compatibilidad (mongo_compat.py) arma el SQL JSONB
a mano sobre este pool.
"""

import os
import json
import logging
from datetime import datetime, date

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


# ---------------------------------------------------------------------------
# Serialización JSON tolerante: las fechas se guardan como ISO-8601 (igual que
# la convención del código original que usa datetime.isoformat()).
# ---------------------------------------------------------------------------
def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _json_dumps(value) -> str:
    return json.dumps(value, default=_json_default)


def _json_loads(value: str):
    return json.loads(value)


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Registra el codec JSONB para que asyncpg entregue/acepte objetos Python."""
    await conn.set_type_codec(
        "jsonb",
        encoder=_json_dumps,
        decoder=_json_loads,
        schema="pg_catalog",
    )


def _normalize_dsn(dsn: str) -> str:
    """asyncpg no entiende el sufijo de driver de SQLAlchemy (+asyncpg/+psycopg)."""
    return (
        dsn.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
        .replace("postgres+asyncpg://", "postgresql://")
    )


async def init_pool() -> asyncpg.Pool:
    """Crea el pool global (idempotente). Llamar en el startup de FastAPI."""
    global _pool
    if _pool is not None:
        return _pool

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL environment variable must be set.")

    _pool = await asyncpg.create_pool(
        dsn=_normalize_dsn(dsn),
        # Pooling agresivo para tráfico masivo:
        min_size=10,        # conexiones calientes desde el arranque
        max_size=100,       # techo para picos de concurrencia
        max_queries=50000,  # recicla la conexión tras N queries (libera memoria)
        max_inactive_connection_lifetime=300.0,
        command_timeout=60,
        init=_init_connection,
    )
    logger.info("PostgreSQL pool inicializado (min=10, max=100, max_queries=50000)")
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Postgres pool no inicializado. Llama init_pool() primero.")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool cerrado")

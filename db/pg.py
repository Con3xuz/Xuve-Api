"""
PostgreSQL connection pool (asyncpg).

Expone un pool global de asyncpg configurado para soportar alta
concurrencia, y un codec JSONB <-> Python para serializar/deserializar
automáticamente documentos como dict/list/escalares en las tablas de Xuve.
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

    # Supabase Session Pooler permite típicamente hasta 15 conexiones en capa gratuita.
    # Usamos min_size=2 y max_size=10 para no agotar el pool de Supabase.
    min_size = int(os.environ.get("DB_POOL_MIN_SIZE", "2"))
    max_size = int(os.environ.get("DB_POOL_MAX_SIZE", "10"))

    _pool = await asyncpg.create_pool(
        dsn=_normalize_dsn(dsn),
        min_size=min_size,
        max_size=max_size,
        max_queries=50000,
        max_inactive_connection_lifetime=300.0,
        command_timeout=60,
        init=_init_connection,
    )
    logger.info(f"PostgreSQL pool inicializado (min={min_size}, max={max_size})")
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

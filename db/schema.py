"""
Esquema PostgreSQL para el almacén documental JSONB de OMNI.

Cada "colección" de MongoDB se mapea a una tabla `omni.<coleccion>` con la forma:
    pk         BIGSERIAL PRIMARY KEY
    doc        JSONB NOT NULL      -- el documento completo
    created_at timestamptz DEFAULT now()

OPTIMIZACIÓN ANTI-ENGORDE (para miles de usuarios concurrentes):
NO se crean índices GIN genéricos sobre todo el JSONB en tablas calientes/de alta
escritura (engordan y penalizan cada INSERT/UPDATE). En su lugar se crean índices
B-Tree EXPRESIONALES sobre las claves realmente consultadas, y restricciones de
unicidad donde el dominio lo exige.
"""

import re
import logging

from db.pg import get_pool

logger = logging.getLogger(__name__)

_VALID_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")

# --- Las ~62 colecciones del ecosistema OMNI (extraídas del código) ----------
COLLECTIONS = [
    "users",
    "user_sessions",
    "email_verifications",
    "password_resets",
    "transactions",
    "wallets",
    "wallet_holds",
    "exchange_rates",
    "platform_config",
    "daily_subscriptions",
    "subscription_history",
    "subscription_payments",
    "services",
    "ratings",
    "drivers",
    "provider_availability",
    "socios_conductores",
    "socios_repartidores",
    "socios_comerciales",
    "socios_carga_pesada",
    "socios_interurbano",
    "store_profiles",
    "market_stores",
    "market_products",
    "market_orders",
    "products",
    "orders",
    "kyc_requests",
    "medicos",
    "prescriptions",
    "notifications",
    "chat_conversations",
    "chat_messages",
    "messages",
    # Rent a Car
    "rent_cars",
    "rent_requests",
    "rent_owners",
    "rent_vehicles",
    "rentals",
    # Carga pesada
    "cotizaciones_carga",
    "vehiculos_carga",
    "servicios_carga",
    "operadores_carga",
    "notificaciones_carga",
    # Líneas interurbanas (B2B)
    "lineas_transporte",
    "vehiculos_linea",
    "choferes_linea",
    "viajes_interurbano",
    "reservas_interurbano",
    "viajes",
    # Rutas / transporte urbano
    "rutas_urbanas",
    "rutas_urbanas_v",
    "lineas_urbanas",
    "vehiculos_urbanos",
    "choferes_urbanos",
    "recorridos_activos",
    "recorridos_urbanos",
    "recorridos_historico",
    "recorridos_urbanos_historico",
    "asignaciones_ruta",
    "asignaciones_urbanas",
    "micropagos_urbanos",
    "micropagos_qr",
    "fixed_routes",
    "rutas",
]

# --- Índices B-Tree expresionales dirigidos (clave: valor caliente) ----------
# Formato: "<coleccion>": [lista de sentencias CREATE INDEX idempotentes].
_INDEXES: dict[str, list[str]] = {
    "users": [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_id ON omni.users ((doc->>'user_id'))",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON omni.users ((doc->>'email'))",
    ],
    "user_sessions": [
        "CREATE INDEX IF NOT EXISTS idx_sessions_token ON omni.user_sessions ((doc->>'session_token'))",
    ],
    "email_verifications": [
        "CREATE INDEX IF NOT EXISTS idx_emailver_email ON omni.email_verifications ((doc->>'email'))",
        "CREATE INDEX IF NOT EXISTS idx_emailver_code ON omni.email_verifications ((doc->>'code'))",
    ],
    "password_resets": [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_pwreset_token ON omni.password_resets ((doc->>'token'))",
        "CREATE INDEX IF NOT EXISTS idx_pwreset_email ON omni.password_resets ((doc->>'email'))",
    ],
    "services": [
        "CREATE INDEX IF NOT EXISTS idx_services_status ON omni.services ((doc->>'status'))",
        "CREATE INDEX IF NOT EXISTS idx_services_user ON omni.services ((doc->>'user_id'))",
    ],
    "transactions": [
        "CREATE INDEX IF NOT EXISTS idx_transactions_user ON omni.transactions ((doc->>'user_id'))",
        "CREATE INDEX IF NOT EXISTS idx_transactions_type ON omni.transactions ((doc->>'type'))",
    ],
    "wallet_holds": [
        "CREATE INDEX IF NOT EXISTS idx_holds_user ON omni.wallet_holds ((doc->>'user_id'))",
        "CREATE INDEX IF NOT EXISTS idx_holds_id ON omni.wallet_holds ((doc->>'hold_id'))",
    ],
    "store_profiles": [
        "CREATE INDEX IF NOT EXISTS idx_store_user ON omni.store_profiles ((doc->>'user_id'))",
        "CREATE INDEX IF NOT EXISTS idx_store_id ON omni.store_profiles ((doc->>'store_id'))",
    ],
    "market_products": [
        "CREATE INDEX IF NOT EXISTS idx_products_store ON omni.market_products ((doc->>'store_id'))",
        "CREATE INDEX IF NOT EXISTS idx_products_id ON omni.market_products ((doc->>'product_id'))",
    ],
    "orders": [
        "CREATE INDEX IF NOT EXISTS idx_orders_store ON omni.orders ((doc->>'store_id'))",
        "CREATE INDEX IF NOT EXISTS idx_orders_user ON omni.orders ((doc->>'user_id'))",
    ],
    "notifications": [
        "CREATE INDEX IF NOT EXISTS idx_notif_user ON omni.notifications ((doc->>'user_id'))",
    ],
    "kyc_requests": [
        "CREATE INDEX IF NOT EXISTS idx_kyc_user ON omni.kyc_requests ((doc->>'user_id'))",
    ],
    "drivers": [
        "CREATE INDEX IF NOT EXISTS idx_drivers_user ON omni.drivers ((doc->>'user_id'))",
    ],
    "socios_conductores": [
        "CREATE INDEX IF NOT EXISTS idx_sc_user ON omni.socios_conductores ((doc->>'user_id'))",
    ],
    "socios_repartidores": [
        "CREATE INDEX IF NOT EXISTS idx_sr_user ON omni.socios_repartidores ((doc->>'user_id'))",
    ],
    "socios_comerciales": [
        "CREATE INDEX IF NOT EXISTS idx_scom_user ON omni.socios_comerciales ((doc->>'user_id'))",
    ],
    "subscription_payments": [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_subpay_ref ON omni.subscription_payments ((doc->>'reference'))",
        "CREATE INDEX IF NOT EXISTS idx_subpay_user ON omni.subscription_payments ((doc->>'user_id'))",
    ],
    "daily_subscriptions": [
        "CREATE INDEX IF NOT EXISTS idx_subs_user ON omni.daily_subscriptions ((doc->>'user_id'))",
    ],
    "chat_conversations": [
        "CREATE INDEX IF NOT EXISTS idx_conv_id ON omni.chat_conversations ((doc->>'conversation_id'))",
    ],
    "chat_messages": [
        "CREATE INDEX IF NOT EXISTS idx_msg_conv ON omni.chat_messages ((doc->>'conversation_id'))",
    ],
    "prescriptions": [
        "CREATE INDEX IF NOT EXISTS idx_presc_user ON omni.prescriptions ((doc->>'user_id'))",
    ],
    "viajes_interurbano": [
        "CREATE INDEX IF NOT EXISTS idx_viajes_status ON omni.viajes_interurbano ((doc->>'status'))",
    ],
}

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS omni.{name} (
    pk         BIGSERIAL PRIMARY KEY,
    doc        JSONB NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
)
"""


def _check(name: str) -> str:
    if not _VALID_NAME.match(name):
        raise ValueError(f"Nombre de colección inválido: {name!r}")
    return name


async def bootstrap_schema() -> None:
    """Crea (idempotente) el schema `omni`, todas las tablas y sus índices."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS omni")
        for name in COLLECTIONS:
            await conn.execute(_TABLE_DDL.format(name=_check(name)))
        for name, statements in _INDEXES.items():
            for stmt in statements:
                try:
                    await conn.execute(stmt)
                except Exception as exc:  # índice único sobre datos sucios, etc.
                    logger.warning("No se pudo crear índice (%s): %s", name, exc)
    logger.info("Esquema OMNI verificado: %d colecciones", len(COLLECTIONS))

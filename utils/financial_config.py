"""
Xuve - Configuración financiera (modelo de suscripción diaria).

Todos los valores viven en la tabla `xuve.platform_settings` (ver
db/migrations/001_catalogs.sql). Aquí NO hay valores por defecto: si falta una
clave se lanza un error claro en vez de usar un número escondido en el código.
"""

from models.catalog_models import PlatformSettingModel


async def get_setting(key: str):
    """Lee un parámetro de plataforma; falla si no existe en la BD."""
    value = await PlatformSettingModel.get_value(key)
    if value is None:
        raise RuntimeError(
            f"Falta el parámetro '{key}' en xuve.platform_settings. "
            "Ejecuta las migraciones (db/migrations)."
        )
    return value


async def get_financial_config() -> dict:
    """Todos los parámetros de plataforma como dict {clave: valor}."""
    return await PlatformSettingModel.get_all()


async def get_toll_amount(vehicle_type: str) -> float:
    """Monto del peaje según el tipo de vehículo."""
    return await get_setting("toll_moto" if vehicle_type == "moto" else "toll_others")


async def get_exchange_rate() -> float:
    """Tasa de cambio USD/VES actual."""
    return await get_setting("exchange_rate")


async def get_fare_config() -> dict:
    """Pisos y costo por km, listos para utils.fare.estimate_fare."""
    config = await get_financial_config()
    keys = ("fare_min_moto", "fare_min_auto", "fare_per_km_moto", "fare_per_km_auto")
    return {k: config[k] for k in keys}


async def get_daily_subscription_fee() -> float:
    """Fee diario de suscripción."""
    return await get_setting("daily_subscription_fee")


async def get_free_trial_days() -> int:
    """Días de prueba gratis."""
    return await get_setting("free_trial_days")


async def get_activation_fee() -> float:
    return await get_setting("activation_fee")


async def get_min_balance_to_activate() -> float:
    return await get_setting("min_balance_activate")


async def get_min_balance_to_connect() -> float:
    return await get_setting("min_balance_connect")


async def get_heavy_transport_commission() -> float:
    return await get_setting("heavy_transport_commission")


async def get_min_balance_heavy_transport() -> float:
    return await get_setting("min_balance_heavy_transport")


# ==========================================
# FUNCIONES DE COMISIÓN - DEPRECADAS
# Mantenidas solo por compatibilidad, retornan 0
# ==========================================


async def get_commission_rate(service_type: str) -> float:
    """
    DEPRECADA - El sistema de comisiones ha sido eliminado.
    Ahora se usa suscripción diaria. Retorna 0 por compatibilidad.
    """
    return 0.0


async def get_urban_fee() -> float:
    """DEPRECADA - El fee urbano ha sido eliminado. Retorna 0 por compatibilidad."""
    return 0.0

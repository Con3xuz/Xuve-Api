"""
Xuve - Configuración Financiera (v2.0 - Modelo de Suscripción)
==============================================================
NOTA: Las comisiones por transacción han sido ELIMINADAS.
El nuevo modelo es: $1 USD/día para socios.

Este archivo mantiene solo:
- Tasa de cambio USD/VES
- Peajes (si aplican)
- Configuración de suscripción diaria
"""

from utils.database import db

# Valores por defecto
DEFAULT_CONFIG = {
    # Tasa de cambio
    "exchange_rate": 50.0,
    # Peajes (solo para información, no se cobran comisiones)
    "toll_moto": 0.50,
    "toll_others": 1.00,
    # Sistema de suscripción diaria (NUEVO MODELO)
    "daily_subscription_fee": 1.00,  # $1 USD por día
    "free_trial_days": 3,  # 3 días gratis para nuevos socios
    # Fee base de delivery (costo del servicio, no comisión)
    "delivery_fee_base": 2.00,
    # Fee de activación de líneas de transporte
    "line_activation_fee": 5.00,
    # ==========================================
    # Comisiones configurables por el admin (descuento del balance del socio).
    # Deben existir aquí para que get_financial_config() las preserve y para
    # evitar KeyError en los módulos que las consultan (p.ej. market).
    # ==========================================
    "commission_transport": 0.10,   # 10% conductores
    "commission_market": 0.12,       # 12% market (comercios)
    "commission_rent": 0.10,         # 10% rent-a-car
    "commission_interurbano": 0.10,  # 10% terminales interurbanos
    "commission_linea": 0.10,        # 10% líneas de transporte
    "urban_fee_fixed": 0.02,         # fee fijo transporte urbano
    # ==========================================
    # Tarifas de viaje P2P (Xuve). 'min' = piso/tarifa mínima; 'per_km' = costo
    # por km por encima del piso. Ver utils/fare.py::estimate_fare.
    # ==========================================
    "fare_min_moto": 1.00,           # piso Moto/Mototaxi: $1.00 USD
    "fare_min_auto": 2.00,           # piso Taxi/Carro: $2.00 USD
    "fare_per_km_moto": 0.30,        # $/km moto (placeholder, ajustable por admin)
    "fare_per_km_auto": 0.50,        # $/km auto (placeholder, ajustable por admin)
}


async def get_financial_config() -> dict:
    """
    Obtener la configuración financiera actual desde la BD.
    Si no existe, retorna los valores por defecto.
    """
    config = await db.platform_config.find_one({"type": "financial"}, {"_id": 0})

    if not config:
        return DEFAULT_CONFIG.copy()

    # Combinar con defaults para asegurar que todos los campos existan
    result = DEFAULT_CONFIG.copy()
    result.update({k: v for k, v in config.items() if k in DEFAULT_CONFIG})
    return result


async def get_toll_amount(vehicle_type: str) -> float:
    """Obtener el monto del peaje según el tipo de vehículo"""
    config = await get_financial_config()
    if vehicle_type == "moto":
        return config["toll_moto"]
    return config["toll_others"]


async def get_exchange_rate() -> float:
    """Obtener la tasa de cambio actual"""
    config = await get_financial_config()
    return config["exchange_rate"]


async def get_fare_config() -> dict:
    """
    Parámetros de tarifa de viaje (pisos y costo por km), listos para
    utils.fare.estimate_fare. Admin-configurables vía platform_config.
    """
    config = await get_financial_config()
    return {
        "fare_min_moto": config["fare_min_moto"],
        "fare_min_auto": config["fare_min_auto"],
        "fare_per_km_moto": config["fare_per_km_moto"],
        "fare_per_km_auto": config["fare_per_km_auto"],
    }


async def get_daily_subscription_fee() -> float:
    """Obtener el fee diario de suscripción"""
    config = await get_financial_config()
    return config.get("daily_subscription_fee", 1.00)


async def get_free_trial_days() -> int:
    """Obtener los días de prueba gratis"""
    config = await get_financial_config()
    return config.get("free_trial_days", 3)


# ==========================================
# FUNCIONES DE COMISIÓN - DEPRECADAS
# Mantenidas solo por compatibilidad, retornan 0
# ==========================================


async def get_commission_rate(service_type: str) -> float:
    """
    DEPRECADA - El sistema de comisiones ha sido eliminado.
    Ahora se usa suscripción diaria de $1 USD.
    Retorna 0 por compatibilidad.
    """
    return 0.0


async def get_urban_fee() -> float:
    """
    DEPRECADA - El fee urbano ha sido eliminado.
    Ahora se usa suscripción diaria de $1 USD.
    Retorna 0 por compatibilidad.
    """
    return 0.0


async def get_activation_fee() -> float:
    """
    DEPRECADA - Usar get_daily_subscription_fee() en su lugar.
    """
    return await get_daily_subscription_fee()


async def get_min_balance_to_activate() -> float:
    """
    El saldo mínimo para activarse es igual al fee diario.
    """
    return await get_daily_subscription_fee()

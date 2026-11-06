"""
Xuve / Xuve — Esqueleto de cálculo de tarifas (mercado P2P).
============================================================
Función BASE para estimar la tarifa de un viaje. Pensada para la dinámica de
pueblos y ciudades pequeñas: hay un "piso" (tarifa mínima) por tipo de vehículo,
y por encima de ese piso se cobra un costo por kilómetro.

Regla inicial (configurable desde financial_config):
    tarifa = max(piso_segun_vehiculo, costo_por_km * km)

- Moto (mototaxi):      piso $1.00 USD
- Auto (taxi / carro):  piso $2.00 USD

Esto es un ESQUELETO: la función es pura (sin IO) para poder testearla sola y
extenderla después con componente por tiempo, recargos nocturnos, surge, peajes,
etc. La config llega como dict (ver utils.financial_config.get_fare_config).
"""

# Tipos de vehículo que tarifan como "moto". El resto (carro_particular,
# taxi_linea, etc.) tarifa como "auto".
MOTO_VEHICLES = {"moto", "mototaxi"}


def is_moto(vehicle_type: str | None) -> bool:
    return (vehicle_type or "").lower() in MOTO_VEHICLES


def estimate_fare(
    distance_m: float | None,
    duration_s: float | None,
    vehicle_type: str | None,
    fare_config: dict,
) -> dict:
    """
    Estima la tarifa de un viaje a partir de la distancia/tiempo (del proxy de
    Directions) y el tipo de vehículo.

    Args:
        distance_m: distancia en metros (de Google Directions).
        duration_s: duración en segundos (reservado para lógica por tiempo).
        vehicle_type: 'mototaxi', 'taxi_linea', 'carro_particular', ...
        fare_config: dict con fare_min_moto / fare_min_auto / fare_per_km_moto /
                     fare_per_km_auto (ver financial_config.get_fare_config).

    Returns:
        dict con el desglose y la tarifa estimada (USD).
    """
    moto = is_moto(vehicle_type)

    min_fare = fare_config["fare_min_moto"] if moto else fare_config["fare_min_auto"]
    per_km = fare_config["fare_per_km_moto"] if moto else fare_config["fare_per_km_auto"]

    km = (distance_m or 0) / 1000.0
    distance_fare = per_km * km

    # Aplica el piso: si el cálculo por distancia no llega al mínimo, cobra el mínimo.
    floor_applied = distance_fare <= min_fare
    estimated = max(min_fare, distance_fare)

    # TODO (futuro): sumar componente por tiempo (duration_s), recargo nocturno,
    # multiplicador de demanda (surge) y peajes según ruta.

    return {
        "vehicle_type": vehicle_type,
        "vehicle_class": "moto" if moto else "auto",
        "currency": "USD",
        "distance_km": round(km, 2),
        "duration_min": round((duration_s or 0) / 60.0, 1),
        "min_fare": round(min_fare, 2),
        "per_km": round(per_km, 2),
        "distance_fare": round(distance_fare, 2),
        "floor_applied": floor_applied,
        "estimated_fare": round(estimated, 2),
    }

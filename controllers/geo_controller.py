"""Controlador de geo - Validaciones y lógica de negocio."""
from models import *
"""
Geo Routes — Proxy seguro hacia Google Maps Platform (Web Services).
====================================================================
Centraliza TODAS las llamadas facturables de geolocalización en el backend
para que la API key NUNCA viaje al cliente.

- La llave vive solo aquí, en GOOGLE_MAPS_SERVER_KEY (backend/.env, idealmente
  AWS Secrets Manager). En GCP debe estar restringida por IP del servidor AWS y
  limitada a: Places API, Directions API, Distance Matrix API, Geocoding API.
- El render del mapa en la app usa una llave DISTINTA (EXPO_PUBLIC_GOOGLE_MAPS_KEY),
  restringida por firma de app y solo a los Maps SDK. Esa nunca toca este módulo.

Todos los endpoints exigen sesión válida (get_current_user) y tienen rate limit
para acotar el gasto si una sesión se ve comprometida.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
import os
import httpx

from utils.auth import get_current_user
from utils.financial_config import get_fare_config
from utils.fare import estimate_fare

# Rate limiting (instancia compartida)
from utils.ratelimit import limiter


GOOGLE_MAPS_SERVER_KEY = os.environ.get("GOOGLE_MAPS_SERVER_KEY", "")
GOOGLE_BASE = "https://maps.googleapis.com/maps/api"

# Sesgo geográfico por defecto: Mérida, Venezuela (núcleo operativo de Xuve).
DEFAULT_LANGUAGE = "es"
DEFAULT_REGION = "ve"
DEFAULT_COMPONENTS = "country:ve"  # cobertura NACIONAL: restringe a Venezuela, sin fijar ciudad
# Radio de sesgo SOLO cuando el cliente envía la ubicación del usuario (GPS).
# Es un "bias" (prioriza lo cercano), no excluye resultados del resto del país.
LOCATION_BIAS_RADIUS_M = 50000


def _require_key() -> str:
    """Falla explícito si la llave de servidor no está configurada."""
    if not GOOGLE_MAPS_SERVER_KEY:
        raise HTTPException(
            status_code=503,
            detail="Geolocalización no configurada: falta GOOGLE_MAPS_SERVER_KEY en el servidor.",
        )
    return GOOGLE_MAPS_SERVER_KEY


async def _google_get(path: str, params: dict) -> dict:
    """GET a Google Maps Web Services, inyectando la key del lado servidor."""
    params = {**params, "key": _require_key()}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{GOOGLE_BASE}/{path}", params=params)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error consultando Google Maps: {e}")

    status = data.get("status")
    # ZERO_RESULTS no es un error: simplemente no hay resultados.
    if status not in ("OK", "ZERO_RESULTS"):
        # No filtramos el error crudo de Google al cliente (puede traer la key en la URL).
        raise HTTPException(status_code=502, detail=f"Google Maps status: {status}")
    return data


def _decode_polyline(encoded: str) -> list[dict]:
    """Decodifica el polyline de Google a [{latitude, longitude}] para react-native-maps."""
    coords: list[dict] = []
    index = lat = lng = 0
    length = len(encoded)
    while index < length:
        for _ in range(2):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if _ == 0:
                lat += delta
            else:
                lng += delta
        coords.append({"latitude": lat / 1e5, "longitude": lng / 1e5})
    return coords


@limiter.limit("30/minute")
async def autocomplete(
    request: Request,
    query: str = Query(..., min_length=2, description="Texto parcial a autocompletar"),
    lat: float | None = Query(None, description="Latitud del usuario (GPS) para sesgar a su zona"),
    lng: float | None = Query(None, description="Longitud del usuario (GPS) para sesgar a su zona"),
    user: dict = Depends(get_current_user),
):
    """Places Autocomplete a nivel NACIONAL (toda Venezuela).

    Restringe a Venezuela (`country:ve`) sin fijar ninguna ciudad. Si el cliente
    envía lat/lng (GPS), sesga los resultados a la zona del usuario —pueblo o
    ciudad grande— sin excluir el resto del país.
    """
    params = {
        "input": query,
        "language": DEFAULT_LANGUAGE,
        "components": DEFAULT_COMPONENTS,
    }
    if lat is not None and lng is not None:
        params["location"] = f"{lat},{lng}"
        params["radius"] = LOCATION_BIAS_RADIUS_M
    data = await _google_get("place/autocomplete/json", params)
    predictions = [
        {
            "place_id": p["place_id"],
            "mainText": p.get("structured_formatting", {}).get("main_text", p.get("description", "")),
            "secondaryText": p.get("structured_formatting", {}).get("secondary_text", ""),
            "description": p.get("description", ""),
        }
        for p in data.get("predictions", [])
    ]
    return {"predictions": predictions}


@limiter.limit("30/minute")
async def place_details(
    request: Request,
    place_id: str,
    user: dict = Depends(get_current_user),
):
    """Place Details — resuelve un place_id a coordenadas + dirección formateada."""
    data = await _google_get(
        "place/details/json",
        {
            "place_id": place_id,
            "language": DEFAULT_LANGUAGE,
            "fields": "place_id,name,formatted_address,geometry",
        },
    )
    result = data.get("result")
    if not result:
        raise HTTPException(status_code=404, detail="Lugar no encontrado")
    loc = result.get("geometry", {}).get("location", {})
    return {
        "place_id": result.get("place_id"),
        "name": result.get("name"),
        "address": result.get("formatted_address", ""),
        "latitude": loc.get("lat"),
        "longitude": loc.get("lng"),
    }


@limiter.limit("30/minute")
async def geocode(
    request: Request,
    address: str = Query(..., min_length=2),
    user: dict = Depends(get_current_user),
):
    """Geocoding — dirección de texto a coordenadas."""
    data = await _google_get(
        "geocode/json",
        {"address": address, "language": DEFAULT_LANGUAGE, "region": DEFAULT_REGION},
    )
    results = [
        {
            "address": r.get("formatted_address", ""),
            "latitude": r["geometry"]["location"]["lat"],
            "longitude": r["geometry"]["location"]["lng"],
        }
        for r in data.get("results", [])
    ]
    return {"results": results}


async def _fetch_route(origin: str, destination: str) -> dict:
    """Consulta Directions y normaliza la primera ruta. Reutilizado por /directions
    y por /estimate-fare para no duplicar la llamada a Google."""
    data = await _google_get(
        "directions/json",
        {
            "origin": origin,
            "destination": destination,
            "mode": "driving",
            "language": DEFAULT_LANGUAGE,
            "region": DEFAULT_REGION,
        },
    )
    routes = data.get("routes", [])
    if not routes:
        raise HTTPException(status_code=404, detail="No se encontró ruta")
    route = routes[0]
    leg = route["legs"][0]
    return {
        "distance_m": leg["distance"]["value"],
        "distance_text": leg["distance"]["text"],
        "duration_s": leg["duration"]["value"],
        "duration_text": leg["duration"]["text"],
        "polyline": _decode_polyline(route["overview_polyline"]["points"]),
    }


@limiter.limit("30/minute")
async def directions(
    request: Request,
    origin: str = Query(..., description="lat,lng del origen"),
    destination: str = Query(..., description="lat,lng del destino"),
    user: dict = Depends(get_current_user),
):
    """Directions — ruta entre dos puntos: distancia, duración y polyline decodificado."""
    return await _fetch_route(origin, destination)


@limiter.limit("30/minute")
async def estimate_fare_endpoint(
    request: Request,
    origin: str = Query(..., description="lat,lng del origen"),
    destination: str = Query(..., description="lat,lng del destino"),
    vehicle_type: str = Query(..., description="mototaxi | taxi_linea | carro_particular"),
    user: dict = Depends(get_current_user),
):
    """
    Estima la tarifa del viaje: calcula la ruta real (Directions) y aplica el
    esqueleto de tarifas (piso por tipo de vehículo + costo por km).
    """
    route = await _fetch_route(origin, destination)
    fare_config = await get_fare_config()
    quote = estimate_fare(
        route["distance_m"], route["duration_s"], vehicle_type, fare_config
    )
    # Devolvemos también los textos legibles de la ruta para la UI.
    quote["distance_text"] = route["distance_text"]
    quote["duration_text"] = route["duration_text"]
    return quote


# Vehículos por defecto a cotizar (coincide con VEHICLE_OPTIONS del frontend).
DEFAULT_QUOTE_VEHICLES = "mototaxi,taxi_linea,carro_particular"


@limiter.limit("30/minute")
async def quote(
    request: Request,
    origin: str = Query(..., description="lat,lng del origen"),
    destination: str = Query(..., description="lat,lng del destino"),
    vehicle_types: str = Query(
        DEFAULT_QUOTE_VEHICLES, description="Tipos de vehículo separados por coma"
    ),
    user: dict = Depends(get_current_user),
):
    """
    Cotización completa en UNA sola llamada a Directions: ruta (polyline + ETA) +
    tarifa estimada por cada tipo de vehículo. Pensado para la pantalla de
    solicitud, donde el usuario compara precios antes de confirmar.
    """
    route = await _fetch_route(origin, destination)
    fare_config = await get_fare_config()
    types = [t.strip() for t in vehicle_types.split(",") if t.strip()]
    fares = [
        estimate_fare(route["distance_m"], route["duration_s"], t, fare_config)
        for t in types
    ]
    return {
        "distance_text": route["distance_text"],
        "duration_text": route["duration_text"],
        "distance_m": route["distance_m"],
        "duration_s": route["duration_s"],
        "polyline": route["polyline"],
        "fares": fares,
    }


@limiter.limit("30/minute")
async def distance_matrix(
    request: Request,
    origins: str = Query(..., description="lat,lng (uno o varios separados por '|')"),
    destinations: str = Query(..., description="lat,lng (uno o varios separados por '|')"),
    user: dict = Depends(get_current_user),
):
    """Distance Matrix — distancia/tiempo entre múltiples orígenes y destinos."""
    data = await _google_get(
        "distancematrix/json",
        {
            "origins": origins,
            "destinations": destinations,
            "mode": "driving",
            "language": DEFAULT_LANGUAGE,
            "region": DEFAULT_REGION,
        },
    )
    rows = []
    for row in data.get("rows", []):
        elements = []
        for el in row.get("elements", []):
            if el.get("status") == "OK":
                elements.append(
                    {
                        "distance_m": el["distance"]["value"],
                        "distance_text": el["distance"]["text"],
                        "duration_s": el["duration"]["value"],
                        "duration_text": el["duration"]["text"],
                    }
                )
            else:
                elements.append({"status": el.get("status")})
        rows.append(elements)
    return {"rows": rows}

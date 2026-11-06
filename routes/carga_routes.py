from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from datetime import datetime, timezone
import uuid

from utils.database import db
from utils.auth import get_current_user
from models.wallet_models import (
    TransactionType,
    HEAVY_TRANSPORT_COMMISSION,
    MIN_BALANCE_HEAVY_TRANSPORT,
)
from pydantic import BaseModel

router = APIRouter(prefix="/carga", tags=["Carga Pesada"])


# ==================== MODELOS DE CARGA PESADA ====================


class CotizacionRequest(BaseModel):
    """Solicitud de cotización para carga pesada"""

    service_type: str  # flete, mudanza, cisterna
    origin_lat: float
    origin_lng: float
    origin_address: str
    destination_lat: float
    destination_lng: float
    destination_address: str
    # Para cisternas
    volume_liters: Optional[int] = None
    # Para fletes/mudanzas
    cargo_size: Optional[str] = None  # pequeño, mediano, grande
    needs_helpers: Optional[int] = 0
    description: Optional[str] = None


class CotizacionResponse(BaseModel):
    cotizacion_id: str
    service_type: str
    base_fare: float
    helpers_cost: float
    total_fare: float
    commission_expected: float


# ==================== TARIFAS PLANAS ====================

# Tarifas fijas por tipo de servicio
TARIFAS_CISTERNA = {
    5000: 20.00,  # 5,000 litros
    10000: 30.00,  # 10,000 litros
    15000: 40.00,  # 15,000 litros
    20000: 50.00,  # 20,000 litros
}

TARIFAS_FLETE = {
    "pequeño": 15.00,  # Camión 350
    "mediano": 25.00,  # Camión 750
    "grande": 40.00,  # Camión cava grande
}

TARIFAS_MUDANZA = {
    "pequeño": 30.00,  # Apartamento pequeño
    "mediano": 50.00,  # Casa mediana
    "grande": 80.00,  # Casa grande
}

COSTO_AYUDANTE = 5.00  # Por ayudante adicional


def calcular_tarifa_cisterna(volume_liters: int) -> float:
    """Calcular tarifa para cisterna según capacidad"""
    for volume, price in sorted(TARIFAS_CISTERNA.items()):
        if volume_liters <= volume:
            return price
    return TARIFAS_CISTERNA[20000]  # Máximo


def calcular_tarifa_flete(cargo_size: str) -> float:
    """Calcular tarifa para flete según tamaño"""
    return TARIFAS_FLETE.get(cargo_size, TARIFAS_FLETE["mediano"])


def calcular_tarifa_mudanza(cargo_size: str) -> float:
    """Calcular tarifa para mudanza según tamaño"""
    return TARIFAS_MUDANZA.get(cargo_size, TARIFAS_MUDANZA["mediano"])


# ==================== ENDPOINTS ====================


@router.post("/cotizacion")
async def crear_cotizacion(
    data: CotizacionRequest, user: dict = Depends(get_current_user)
):
    """
    Crear cotización para servicio de carga pesada.

    NO USA TAXÍMETRO - Tarifas planas según:
    - Cisterna: por capacidad (litros)
    - Flete: por tamaño de carga
    - Mudanza: por tamaño + ayudantes
    """
    # Calcular tarifa base según tipo de servicio
    if data.service_type == "cisterna":
        if not data.volume_liters:
            raise HTTPException(
                status_code=400, detail="Debe especificar los litros para cisterna"
            )
        base_fare = calcular_tarifa_cisterna(data.volume_liters)
    elif data.service_type == "flete":
        base_fare = calcular_tarifa_flete(data.cargo_size or "mediano")
    elif data.service_type == "mudanza":
        base_fare = calcular_tarifa_mudanza(data.cargo_size or "mediano")
    else:
        raise HTTPException(
            status_code=400,
            detail="Tipo de servicio inválido. Use: cisterna, flete, mudanza",
        )

    # Calcular costo de ayudantes
    helpers_cost = (data.needs_helpers or 0) * COSTO_AYUDANTE

    # Total
    total_fare = base_fare + helpers_cost

    # Comisión esperada (10%)
    commission_expected = total_fare * HEAVY_TRANSPORT_COMMISSION

    cotizacion_doc = {
        "cotizacion_id": f"cot_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "service_type": data.service_type,
        "origin": {
            "lat": data.origin_lat,
            "lng": data.origin_lng,
            "address": data.origin_address,
        },
        "destination": {
            "lat": data.destination_lat,
            "lng": data.destination_lng,
            "address": data.destination_address,
        },
        "volume_liters": data.volume_liters,
        "cargo_size": data.cargo_size,
        "needs_helpers": data.needs_helpers,
        "description": data.description,
        "base_fare": base_fare,
        "helpers_cost": helpers_cost,
        "total_fare": total_fare,
        "commission_expected": commission_expected,
        "status": "pending",  # pending, sent_to_drivers, accepted, in_progress, completed, cancelled
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.cotizaciones_carga.insert_one(cotizacion_doc)

    if "_id" in cotizacion_doc:
        del cotizacion_doc["_id"]

    return cotizacion_doc


@router.post("/cotizacion/{cotizacion_id}/enviar")
async def enviar_cotizacion_a_conductores(
    cotizacion_id: str, user: dict = Depends(get_current_user)
):
    """
    Enviar cotización a conductores de carga pesada.

    DYNAMIC WALLET GUARD:
    Solo se notifica a conductores cuyo balance_usd >= comisión esperada.
    Si el viaje cuesta $50, el chofer debe tener al menos $5.00 (10%) en su wallet.
    """
    cotizacion = await db.cotizaciones_carga.find_one(
        {"cotizacion_id": cotizacion_id}, {"_id": 0}
    )
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if cotizacion["status"] != "pending":
        raise HTTPException(status_code=400, detail="Esta cotización ya fue procesada")

    commission_required = cotizacion["commission_expected"]

    # DYNAMIC WALLET GUARD: Buscar conductores con saldo >= comisión esperada
    # Primero obtener todos los socios de carga pesada aprobados
    socios_carga = await db.socios_carga_pesada.find(
        {"status": "approved", "is_online": True, "activation_fee_paid": True},
        {"_id": 0},
    ).to_list(100)

    # Filtrar por balance suficiente
    conductores_elegibles = []
    for socio in socios_carga:
        wallet_user = await db.users.find_one({"user_id": socio["user_id"]}, {"_id": 0})
        if wallet_user:
            available_balance = wallet_user.get("wallet_balance", 0) - wallet_user.get(
                "wallet_held", 0
            )
            if available_balance >= commission_required:
                conductores_elegibles.append(
                    {
                        "socio_id": socio["socio_id"],
                        "user_id": socio["user_id"],
                        "vehicle_type": socio.get("vehicle_type"),
                        "balance": available_balance,
                    }
                )

    # Crear notificaciones para conductores elegibles
    notification_count = 0
    for conductor in conductores_elegibles:
        await db.notificaciones_carga.insert_one(
            {
                "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
                "cotizacion_id": cotizacion_id,
                "conductor_id": conductor["socio_id"],
                "user_id": conductor["user_id"],
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        notification_count += 1

    # Actualizar estado de la cotización
    await db.cotizaciones_carga.update_one(
        {"cotizacion_id": cotizacion_id},
        {
            "$set": {
                "status": "sent_to_drivers",
                "conductores_notificados": notification_count,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {
        "message": f"Cotización enviada a {notification_count} conductores elegibles",
        "cotizacion_id": cotizacion_id,
        "commission_required": commission_required,
        "conductores_elegibles": notification_count,
    }


@router.post("/cotizacion/{cotizacion_id}/aceptar")
async def aceptar_cotizacion(
    cotizacion_id: str, user: dict = Depends(get_current_user)
):
    """
    Conductor acepta una cotización de carga pesada.

    Verifica que el conductor tenga saldo suficiente para la comisión.
    """
    cotizacion = await db.cotizaciones_carga.find_one(
        {"cotizacion_id": cotizacion_id}, {"_id": 0}
    )
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if cotizacion["status"] not in ["pending", "sent_to_drivers"]:
        raise HTTPException(
            status_code=400, detail="Esta cotización ya fue asignada o completada"
        )

    # Verificar que el usuario es socio de carga pesada
    socio = await db.socios_carga_pesada.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(
            status_code=403, detail="No eres un socio de carga pesada registrado"
        )

    # DYNAMIC WALLET GUARD: Verificar saldo
    commission_required = cotizacion["commission_expected"]
    available_balance = user.get("wallet_balance", 0) - user.get("wallet_held", 0)

    if available_balance < commission_required:
        raise HTTPException(
            status_code=403,
            detail=f"Saldo insuficiente. Necesitas ${commission_required:.2f} para aceptar este servicio. Tu saldo: ${available_balance:.2f}",
        )

    # Asignar conductor a la cotización
    await db.cotizaciones_carga.update_one(
        {"cotizacion_id": cotizacion_id},
        {
            "$set": {
                "driver_id": socio["socio_id"],
                "driver_user_id": user["user_id"],
                "status": "accepted",
                "accepted_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {
        "message": "Cotización aceptada",
        "cotizacion_id": cotizacion_id,
        "total_fare": cotizacion["total_fare"],
        "commission_on_completion": commission_required,
    }


@router.post("/cotizacion/{cotizacion_id}/completar")
async def completar_servicio_carga(
    cotizacion_id: str, user: dict = Depends(get_current_user)
):
    """
    Marcar servicio de carga pesada como completado.

    CASH-TO-DRIVER: El cliente paga 100% al camionero al llegar.
    OMNI descuenta 10% de comisión del balance del conductor.
    """
    cotizacion = await db.cotizaciones_carga.find_one(
        {"cotizacion_id": cotizacion_id}, {"_id": 0}
    )
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if cotizacion["status"] != "accepted":
        raise HTTPException(status_code=400, detail="Este servicio no está en progreso")

    # Verificar que el usuario es el conductor asignado
    if cotizacion.get("driver_user_id") != user["user_id"]:
        raise HTTPException(
            status_code=403, detail="No eres el conductor asignado a este servicio"
        )

    # Cobrar comisión del 10%
    commission = cotizacion["commission_expected"]

    await db.users.update_one(
        {"user_id": user["user_id"]}, {"$inc": {"wallet_balance": -commission}}
    )

    # Registrar transacción
    await db.transactions.insert_one(
        {
            "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"],
            "amount_usd": -commission,
            "type": TransactionType.COMMISSION_DEDUCTION.value,
            "status": "completed",
            "reference": cotizacion_id,
            "description": f"Comisión {int(HEAVY_TRANSPORT_COMMISSION*100)}% Carga Pesada - Servicio #{cotizacion_id[-6:]} - Tarifa ${cotizacion['total_fare']:.2f}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Actualizar cotización
    await db.cotizaciones_carga.update_one(
        {"cotizacion_id": cotizacion_id},
        {
            "$set": {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "commission_charged": commission,
            }
        },
    )

    # Actualizar estadísticas del socio
    await db.socios_carga_pesada.update_one(
        {"user_id": user["user_id"]},
        {
            "$inc": {
                "total_trips": 1,
                "total_earnings": cotizacion["total_fare"] - commission,
            }
        },
    )

    # Obtener nuevo balance
    updated_user = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})

    return {
        "message": "Servicio completado",
        "total_fare": cotizacion["total_fare"],
        "commission_charged": commission,
        "net_earnings": cotizacion["total_fare"] - commission,
        "new_wallet_balance": updated_user.get("wallet_balance", 0),
    }


@router.get("/mis-cotizaciones")
async def get_mis_cotizaciones(user: dict = Depends(get_current_user)):
    """Obtener cotizaciones del usuario (cliente)"""
    cotizaciones = (
        await db.cotizaciones_carga.find({"user_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )
    return cotizaciones


@router.get("/servicios-disponibles")
async def get_servicios_disponibles(user: dict = Depends(get_current_user)):
    """
    Obtener servicios de carga pesada disponibles para el conductor.

    DYNAMIC WALLET GUARD: Solo muestra servicios donde el conductor
    tiene saldo >= comisión esperada.
    """
    # Verificar que es socio de carga pesada
    socio = await db.socios_carga_pesada.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(status_code=403, detail="No eres un socio de carga pesada")

    # Obtener balance disponible
    available_balance = user.get("wallet_balance", 0) - user.get("wallet_held", 0)

    # Buscar cotizaciones pendientes donde la comisión <= balance
    cotizaciones = (
        await db.cotizaciones_carga.find(
            {
                "status": {"$in": ["pending", "sent_to_drivers"]},
                "driver_id": None,
                "commission_expected": {"$lte": available_balance},
            },
            {"_id": 0},
        )
        .sort("created_at", -1)
        .to_list(50)
    )

    return {
        "available_balance": available_balance,
        "min_recommended_balance": MIN_BALANCE_HEAVY_TRANSPORT,
        "servicios": cotizaciones,
    }


@router.get("/tarifas")
async def get_tarifas():
    """Obtener tarifas de carga pesada"""
    return {
        "cisterna": TARIFAS_CISTERNA,
        "flete": TARIFAS_FLETE,
        "mudanza": TARIFAS_MUDANZA,
        "costo_ayudante": COSTO_AYUDANTE,
        "commission_rate": f"{int(HEAVY_TRANSPORT_COMMISSION*100)}%",
    }

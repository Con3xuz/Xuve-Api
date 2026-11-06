from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid

from utils.database import db
from utils.auth import get_current_user
from utils.financial_config import get_commission_rate
from models.wallet_models import TransactionType

router = APIRouter(prefix="/interurbano", tags=["Transporte Interurbano"])


# ==================== MODELOS ====================


class ViajeCreate(BaseModel):
    """Crear un viaje programado"""

    origen: str
    destino: str
    fecha_salida: str  # ISO format: 2026-03-15T08:00:00
    precio_asiento: float
    capacidad_total: int
    descripcion: Optional[str] = None
    punto_encuentro: Optional[str] = None


class CompraBoletosRequest(BaseModel):
    """Solicitud de compra de boletos"""

    viaje_id: str
    cantidad_puestos: int
    nombre_pasajero: Optional[str] = None
    telefono_pasajero: Optional[str] = None


# ==================== ENDPOINTS PARA LÍNEA DE TRANSPORTE ====================


@router.post("/viajes")
async def crear_viaje(data: ViajeCreate, user: dict = Depends(get_current_user)):
    """
    Crear un viaje programado (Terminal Digital).

    WALLET GUARD: La línea debe tener saldo >= comisión configurada de la capacidad total.
    """
    # Verificar que es socio de transporte interurbano
    socio = await db.socios_interurbano.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(
            status_code=403,
            detail="No eres un operador de transporte interurbano registrado",
        )

    if socio["status"] != "approved":
        raise HTTPException(status_code=403, detail="Tu perfil debe estar aprobado")

    # Obtener tasa de comisión desde la configuración del admin
    commission_rate = await get_commission_rate("interurbano")

    # WALLET GUARD: Calcular comisión potencial máxima
    ingreso_potencial = data.precio_asiento * data.capacidad_total
    comision_maxima = ingreso_potencial * commission_rate

    available_balance = user.get("wallet_balance", 0) - user.get("wallet_held", 0)

    if available_balance < comision_maxima:
        raise HTTPException(
            status_code=403,
            detail=f"Saldo insuficiente para publicar viaje. Necesitas ${comision_maxima:.2f} ({int(commission_rate*100)}% de ${ingreso_potencial:.2f}) para cubrir la comisión potencial. Tu saldo: ${available_balance:.2f}",
        )

    viaje_doc = {
        "viaje_id": f"viaje_{uuid.uuid4().hex[:12]}",
        "linea_id": socio["socio_id"],
        "linea_user_id": user["user_id"],
        "linea_nombre": socio.get("linea_nombre", user.get("name")),
        "origen": data.origen,
        "destino": data.destino,
        "fecha_salida": data.fecha_salida,
        "precio_asiento": data.precio_asiento,
        "capacidad_total": data.capacidad_total,
        "puestos_disponibles": data.capacidad_total,
        "puestos_vendidos": 0,
        "descripcion": data.descripcion,
        "punto_encuentro": data.punto_encuentro,
        "ingreso_potencial": ingreso_potencial,
        "comision_esperada": comision_maxima,
        "status": "programado",  # programado, en_curso, completado, cancelado
        "reservas": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.viajes_interurbano.insert_one(viaje_doc)

    if "_id" in viaje_doc:
        del viaje_doc["_id"]

    return {"message": "Viaje programado creado exitosamente", "viaje": viaje_doc}


@router.get("/mis-viajes")
async def get_mis_viajes(user: dict = Depends(get_current_user)):
    """Obtener viajes de la línea de transporte"""
    socio = await db.socios_interurbano.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not socio:
        raise HTTPException(
            status_code=403, detail="No eres operador de transporte interurbano"
        )

    viajes = (
        await db.viajes_interurbano.find({"linea_id": socio["socio_id"]}, {"_id": 0})
        .sort("fecha_salida", 1)
        .to_list(100)
    )

    return viajes


@router.post("/viajes/{viaje_id}/iniciar")
async def iniciar_viaje(viaje_id: str, user: dict = Depends(get_current_user)):
    """Marcar viaje como en curso"""
    viaje = await db.viajes_interurbano.find_one({"viaje_id": viaje_id}, {"_id": 0})
    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")

    if viaje["linea_user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    await db.viajes_interurbano.update_one(
        {"viaje_id": viaje_id},
        {
            "$set": {
                "status": "en_curso",
                "iniciado_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": "Viaje iniciado"}


@router.post("/viajes/{viaje_id}/completar")
async def completar_viaje(viaje_id: str, user: dict = Depends(get_current_user)):
    """
    Completar viaje y cobrar comisión.

    El cliente paga directo al chofer (cash).
    Xuve cobra el % configurado del total de boletos vendidos de la wallet de la línea.
    """
    viaje = await db.viajes_interurbano.find_one({"viaje_id": viaje_id}, {"_id": 0})
    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")

    if viaje["linea_user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    if viaje["status"] == "completado":
        raise HTTPException(status_code=400, detail="Este viaje ya fue completado")

    # Obtener tasa de comisión desde la configuración del admin
    commission_rate = await get_commission_rate("interurbano")

    # Calcular comisión real basada en boletos vendidos
    ingresos_reales = viaje["puestos_vendidos"] * viaje["precio_asiento"]
    comision = ingresos_reales * commission_rate

    # Descontar comisión de la wallet
    await db.users.update_one(
        {"user_id": user["user_id"]}, {"$inc": {"wallet_balance": -comision}}
    )

    # Registrar transacción
    await db.transactions.insert_one(
        {
            "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"],
            "amount_usd": -comision,
            "type": TransactionType.COMMISSION_DEDUCTION.value,
            "status": "completed",
            "reference": viaje_id,
            "description": f"Comisión {int(commission_rate*100)}% - Viaje {viaje['origen']}-{viaje['destino']} - {viaje['puestos_vendidos']} boletos (${ingresos_reales:.2f})",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Actualizar viaje
    await db.viajes_interurbano.update_one(
        {"viaje_id": viaje_id},
        {
            "$set": {
                "status": "completado",
                "completado_at": datetime.now(timezone.utc).isoformat(),
                "ingresos_reales": ingresos_reales,
                "comision_cobrada": comision,
            }
        },
    )

    # Actualizar estadísticas del socio
    await db.socios_interurbano.update_one(
        {"socio_id": viaje["linea_id"]},
        {
            "$inc": {
                "total_viajes": 1,
                "total_pasajeros": viaje["puestos_vendidos"],
                "total_earnings": ingresos_reales - comision,
            }
        },
    )

    return {
        "message": "Viaje completado",
        "puestos_vendidos": viaje["puestos_vendidos"],
        "ingresos_totales": ingresos_reales,
        "comision_cobrada": comision,
        "ganancias_netas": ingresos_reales - comision,
    }


@router.delete("/viajes/{viaje_id}")
async def cancelar_viaje(viaje_id: str, user: dict = Depends(get_current_user)):
    """Cancelar un viaje programado"""
    viaje = await db.viajes_interurbano.find_one({"viaje_id": viaje_id}, {"_id": 0})
    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")

    if viaje["linea_user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    if viaje["puestos_vendidos"] > 0:
        raise HTTPException(
            status_code=400,
            detail="No puedes cancelar un viaje con boletos vendidos. Contacta a los pasajeros primero.",
        )

    await db.viajes_interurbano.update_one(
        {"viaje_id": viaje_id},
        {
            "$set": {
                "status": "cancelado",
                "cancelado_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": "Viaje cancelado"}


# ==================== ENDPOINTS PARA CLIENTES ====================


@router.get("/viajes/buscar")
async def buscar_viajes(
    origen: Optional[str] = None,
    destino: Optional[str] = None,
    fecha: Optional[str] = None,
):
    """
    Buscar viajes disponibles.
    Filtros opcionales: origen, destino, fecha
    """
    query = {"status": "programado", "puestos_disponibles": {"$gt": 0}}

    if origen:
        query["origen"] = {"$regex": origen, "$options": "i"}
    if destino:
        query["destino"] = {"$regex": destino, "$options": "i"}
    if fecha:
        # Buscar viajes del día especificado
        query["fecha_salida"] = {"$regex": f"^{fecha}"}

    viajes = (
        await db.viajes_interurbano.find(query, {"_id": 0, "reservas": 0})
        .sort("fecha_salida", 1)
        .to_list(50)
    )

    return viajes


@router.get("/viajes/{viaje_id}")
async def get_viaje(viaje_id: str):
    """Obtener detalles de un viaje"""
    viaje = await db.viajes_interurbano.find_one({"viaje_id": viaje_id}, {"_id": 0})
    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    return viaje


@router.post("/viajes/{viaje_id}/comprar")
async def comprar_boletos(
    viaje_id: str, data: CompraBoletosRequest, user: dict = Depends(get_current_user)
):
    """
    Comprar boletos para un viaje.

    El cliente reserva N puestos y paga al chofer al abordar (cash).
    Se descuentan los puestos del inventario.
    """
    viaje = await db.viajes_interurbano.find_one({"viaje_id": viaje_id}, {"_id": 0})
    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")

    if viaje["status"] != "programado":
        raise HTTPException(
            status_code=400, detail="Este viaje ya no está disponible para reservas"
        )

    if data.cantidad_puestos <= 0:
        raise HTTPException(status_code=400, detail="Cantidad de puestos inválida")

    if data.cantidad_puestos > viaje["puestos_disponibles"]:
        raise HTTPException(
            status_code=400,
            detail=f"Solo quedan {viaje['puestos_disponibles']} puestos disponibles",
        )

    # Calcular total
    total = data.cantidad_puestos * viaje["precio_asiento"]

    # Crear reserva
    reserva_id = f"res_{uuid.uuid4().hex[:12]}"
    reserva = {
        "reserva_id": reserva_id,
        "user_id": user["user_id"],
        "nombre_pasajero": data.nombre_pasajero or user.get("name"),
        "telefono_pasajero": data.telefono_pasajero or user.get("phone"),
        "cantidad_puestos": data.cantidad_puestos,
        "precio_unitario": viaje["precio_asiento"],
        "total": total,
        "status": "confirmada",  # El pago es al abordar
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Actualizar viaje
    await db.viajes_interurbano.update_one(
        {"viaje_id": viaje_id},
        {
            "$push": {"reservas": reserva},
            "$inc": {
                "puestos_disponibles": -data.cantidad_puestos,
                "puestos_vendidos": data.cantidad_puestos,
            },
        },
    )

    # Guardar reserva del usuario
    await db.reservas_interurbano.insert_one(
        {
            **reserva,
            "viaje_id": viaje_id,
            "origen": viaje["origen"],
            "destino": viaje["destino"],
            "fecha_salida": viaje["fecha_salida"],
            "linea_nombre": viaje["linea_nombre"],
            "punto_encuentro": viaje.get("punto_encuentro"),
        }
    )

    return {
        "message": f"¡Reserva confirmada! {data.cantidad_puestos} puesto(s) reservado(s)",
        "reserva_id": reserva_id,
        "viaje": {
            "origen": viaje["origen"],
            "destino": viaje["destino"],
            "fecha_salida": viaje["fecha_salida"],
            "punto_encuentro": viaje.get("punto_encuentro"),
        },
        "detalles": {
            "cantidad_puestos": data.cantidad_puestos,
            "precio_unitario": viaje["precio_asiento"],
            "total_a_pagar": total,
        },
        "nota": "Paga el total al chofer al momento de abordar (Efectivo o Pago Móvil)",
    }


@router.get("/mis-reservas")
async def get_mis_reservas(user: dict = Depends(get_current_user)):
    """Obtener reservas del usuario"""
    reservas = (
        await db.reservas_interurbano.find({"user_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )

    return reservas


@router.delete("/reservas/{reserva_id}")
async def cancelar_reserva(reserva_id: str, user: dict = Depends(get_current_user)):
    """Cancelar una reserva (devuelve puestos al inventario)"""
    reserva = await db.reservas_interurbano.find_one(
        {"reserva_id": reserva_id, "user_id": user["user_id"]}, {"_id": 0}
    )

    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    # Verificar que el viaje no haya iniciado
    viaje = await db.viajes_interurbano.find_one(
        {"viaje_id": reserva["viaje_id"]}, {"_id": 0}
    )
    if viaje and viaje["status"] != "programado":
        raise HTTPException(
            status_code=400,
            detail="No puedes cancelar reservas de viajes en curso o completados",
        )

    # Devolver puestos al inventario
    await db.viajes_interurbano.update_one(
        {"viaje_id": reserva["viaje_id"]},
        {
            "$pull": {"reservas": {"reserva_id": reserva_id}},
            "$inc": {
                "puestos_disponibles": reserva["cantidad_puestos"],
                "puestos_vendidos": -reserva["cantidad_puestos"],
            },
        },
    )

    # Marcar reserva como cancelada
    await db.reservas_interurbano.update_one(
        {"reserva_id": reserva_id},
        {
            "$set": {
                "status": "cancelada",
                "cancelada_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": "Reserva cancelada. Los puestos han sido liberados."}


# ==================== RUTAS POPULARES ====================


@router.get("/rutas-populares")
async def get_rutas_populares():
    """Obtener rutas populares con viajes próximos"""
    # Agregación para obtener rutas con más viajes
    pipeline = [
        {"$match": {"status": "programado", "puestos_disponibles": {"$gt": 0}}},
        {
            "$group": {
                "_id": {"origen": "$origen", "destino": "$destino"},
                "viajes_count": {"$sum": 1},
                "precio_min": {"$min": "$precio_asiento"},
                "proximo_viaje": {"$min": "$fecha_salida"},
            }
        },
        {"$sort": {"viajes_count": -1}},
        {"$limit": 10},
    ]

    rutas = await db.viajes_interurbano.aggregate(pipeline).to_list(10)

    return [
        {
            "origen": r["_id"]["origen"],
            "destino": r["_id"]["destino"],
            "viajes_disponibles": r["viajes_count"],
            "desde": r["precio_min"],
            "proximo": r["proximo_viaje"],
        }
        for r in rutas
    ]

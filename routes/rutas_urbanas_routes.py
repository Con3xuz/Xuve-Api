"""
Rutas Urbanas - Transporte Público Masivo (Micropagos QR)

Este módulo implementa:
1. Gestión de Rutas Urbanas (line_admin)
2. Geolocalización en tiempo real de choferes
3. Torniquete Digital (QR estático)
4. Micropagos con fee fijo

Modelo de Negocio:
- Fee fijo por transacción: configurable desde panel admin
- Cliente paga tarifa → OMNI retiene fee → Línea recibe resto
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import json

from utils.database import db
from utils.auth import get_current_user
from utils.financial_config import get_urban_fee
from models.line_models import RutaUrbanaCreateExtended, AsignacionRuta, GeoUpdate

router = APIRouter(prefix="/rutas-urbanas", tags=["Rutas Urbanas - Transporte Público"])


# ==================== HELPERS ====================


async def get_linea_by_admin(user_id: str):
    """Obtener la línea administrada por un usuario"""
    linea = await db.lineas_transporte.find_one({"admin_user_id": user_id}, {"_id": 0})
    return linea


async def verify_line_admin(user: dict):
    """Verificar que el usuario es line_admin"""
    if user["role"] != "line_admin" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    linea = await get_linea_by_admin(user["user_id"])
    if not linea:
        raise HTTPException(status_code=404, detail="No tienes una línea registrada")

    return linea


async def get_chofer_assignment(chofer_id: str):
    """Obtener la asignación de ruta de un chofer"""
    asignacion = await db.asignaciones_ruta.find_one(
        {"chofer_id": chofer_id, "status": "active"}, {"_id": 0}
    )
    return asignacion


# ==================== GESTIÓN DE RUTAS (PANEL LINE_ADMIN) ====================


@router.post("/rutas")
async def crear_ruta(
    data: RutaUrbanaCreateExtended, user: dict = Depends(get_current_user)
):
    """Crear una nueva ruta urbana"""
    linea = await verify_line_admin(user)

    # Verificar código único
    existing = await db.rutas_urbanas.find_one(
        {"linea_id": linea["linea_id"], "codigo_ruta": data.codigo_ruta.upper()}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya existe una ruta con este código"
        )

    ruta_id = f"ruta_{uuid.uuid4().hex[:12]}"

    ruta_doc = {
        "ruta_id": ruta_id,
        "linea_id": linea["linea_id"],
        "linea_nombre": linea["nombre_linea"],
        "nombre_ruta": data.nombre_ruta,
        "codigo_ruta": data.codigo_ruta.upper(),
        "tarifa": data.tarifa,
        "descripcion": data.descripcion,
        "horario_inicio": data.horario_inicio,
        "horario_fin": data.horario_fin,
        "color": data.color or "#8B5CF6",
        # Asignaciones (se llenan después)
        "asignaciones": [],  # [{chofer_id, vehiculo_id, chofer_nombre, vehiculo_placa}]
        # Estadísticas
        "total_pasajes_hoy": 0,
        "total_ingresos_hoy": float(0),
        "total_pasajes_historico": 0,
        "total_ingresos_historico": float(0),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.rutas_urbanas.insert_one(ruta_doc)

    if "_id" in ruta_doc:
        del ruta_doc["_id"]

    return {"message": "Ruta creada exitosamente", "ruta": ruta_doc}


@router.get("/rutas")
async def listar_rutas(user: dict = Depends(get_current_user)):
    """Listar rutas urbanas de mi línea"""
    linea = await verify_line_admin(user)

    rutas = await db.rutas_urbanas.find(
        {"linea_id": linea["linea_id"]}, {"_id": 0}
    ).to_list(50)

    return rutas


@router.delete("/rutas/{ruta_id}")
async def eliminar_ruta(ruta_id: str, user: dict = Depends(get_current_user)):
    """Eliminar una ruta urbana"""
    linea = await verify_line_admin(user)

    # Verificar que no haya recorridos activos
    recorrido_activo = await db.recorridos_activos.find_one({"ruta_id": ruta_id})
    if recorrido_activo:
        raise HTTPException(
            status_code=400, detail="No puedes eliminar una ruta con recorridos activos"
        )

    result = await db.rutas_urbanas.delete_one(
        {"ruta_id": ruta_id, "linea_id": linea["linea_id"]}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    # Eliminar asignaciones
    await db.asignaciones_ruta.delete_many({"ruta_id": ruta_id})

    return {"message": "Ruta eliminada"}


@router.post("/rutas/{ruta_id}/asignar")
async def asignar_chofer_vehiculo(
    ruta_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """Asignar un chofer y vehículo a una ruta"""
    linea = await verify_line_admin(user)
    body = await request.json()

    chofer_id = body.get("chofer_id")
    vehiculo_id = body.get("vehiculo_id")

    if not chofer_id or not vehiculo_id:
        raise HTTPException(
            status_code=400, detail="chofer_id y vehiculo_id son requeridos"
        )

    # Verificar que la ruta existe
    ruta = await db.rutas_urbanas.find_one(
        {"ruta_id": ruta_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    # Verificar chofer
    chofer = await db.choferes_linea.find_one(
        {"chofer_id": chofer_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not chofer:
        raise HTTPException(status_code=404, detail="Chofer no encontrado")

    # Verificar vehículo
    vehiculo = await db.vehiculos_linea.find_one(
        {"vehiculo_id": vehiculo_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    # Verificar que no esté ya asignado a otra ruta activa
    asignacion_existente = await db.asignaciones_ruta.find_one(
        {"chofer_id": chofer_id, "status": "active"}
    )

    if asignacion_existente and asignacion_existente["ruta_id"] != ruta_id:
        raise HTTPException(
            status_code=400,
            detail=f"Este chofer ya está asignado a la ruta {asignacion_existente['ruta_codigo']}",
        )

    asignacion_id = f"asig_{uuid.uuid4().hex[:12]}"

    asignacion_doc = {
        "asignacion_id": asignacion_id,
        "ruta_id": ruta_id,
        "ruta_nombre": ruta["nombre_ruta"],
        "ruta_codigo": ruta["codigo_ruta"],
        "linea_id": linea["linea_id"],
        "chofer_id": chofer_id,
        "chofer_nombre": chofer["nombre"],
        "chofer_telefono": chofer["telefono"],
        "vehiculo_id": vehiculo_id,
        "vehiculo_placa": vehiculo["placa"],
        "tarifa": ruta["tarifa"],
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Upsert: actualizar si ya existe, crear si no
    await db.asignaciones_ruta.update_one(
        {"chofer_id": chofer_id, "ruta_id": ruta_id},
        {"$set": asignacion_doc},
        upsert=True,
    )

    # Actualizar lista de asignaciones en la ruta
    nueva_asignacion = {
        "chofer_id": chofer_id,
        "chofer_nombre": chofer["nombre"],
        "vehiculo_id": vehiculo_id,
        "vehiculo_placa": vehiculo["placa"],
    }

    # Verificar si ya está en la lista
    asignaciones_actuales = ruta.get("asignaciones", [])
    ya_existe = any(a["chofer_id"] == chofer_id for a in asignaciones_actuales)

    if not ya_existe:
        await db.rutas_urbanas.update_one(
            {"ruta_id": ruta_id}, {"$push": {"asignaciones": nueva_asignacion}}
        )

    return {"message": f"Chofer {chofer['nombre']} asignado a {ruta['nombre_ruta']}"}


@router.delete("/rutas/{ruta_id}/asignar/{chofer_id}")
async def desasignar_chofer(
    ruta_id: str, chofer_id: str, user: dict = Depends(get_current_user)
):
    """Desasignar un chofer de una ruta"""
    linea = await verify_line_admin(user)

    # Verificar que no tenga recorrido activo
    recorrido = await db.recorridos_activos.find_one(
        {"ruta_id": ruta_id, "chofer_id": chofer_id}
    )

    if recorrido:
        raise HTTPException(
            status_code=400,
            detail="No puedes desasignar un chofer con recorrido activo",
        )

    # Eliminar asignación
    await db.asignaciones_ruta.delete_one({"ruta_id": ruta_id, "chofer_id": chofer_id})

    # Actualizar ruta
    await db.rutas_urbanas.update_one(
        {"ruta_id": ruta_id}, {"$pull": {"asignaciones": {"chofer_id": chofer_id}}}
    )

    return {"message": "Chofer desasignado de la ruta"}


# ==================== PANEL DEL CHOFER (GEOLOCALIZACIÓN Y QR) ====================


@router.get("/mi-asignacion")
async def get_mi_asignacion(user: dict = Depends(get_current_user)):
    """
    Obtener la asignación de ruta del chofer actual.
    El chofer debe tener user_id vinculado.
    """
    # Buscar chofer por user_id
    chofer = await db.choferes_linea.find_one({"user_id": user["user_id"]}, {"_id": 0})

    if not chofer:
        # Buscar por email como fallback
        chofer = await db.choferes_linea.find_one({"email": user["email"]}, {"_id": 0})

    if not chofer:
        raise HTTPException(
            status_code=404, detail="No estás registrado como chofer de ninguna línea"
        )

    # Buscar asignación activa
    asignacion = await db.asignaciones_ruta.find_one(
        {"chofer_id": chofer["chofer_id"], "status": "active"}, {"_id": 0}
    )

    if not asignacion:
        return {"asignacion": None, "chofer": chofer}

    # Buscar recorrido activo
    recorrido = await db.recorridos_activos.find_one(
        {"chofer_id": chofer["chofer_id"]}, {"_id": 0}
    )

    return {"asignacion": asignacion, "chofer": chofer, "recorrido_activo": recorrido}


@router.post("/iniciar-recorrido")
async def iniciar_recorrido(request: Request, user: dict = Depends(get_current_user)):
    """
    Iniciar un recorrido en una ruta urbana.
    Genera el QR estático para cobrar pasajes.
    """
    body = await request.json()
    lat = body.get("lat", 0)
    lng = body.get("lng", 0)

    # Buscar chofer
    chofer = await db.choferes_linea.find_one({"user_id": user["user_id"]}, {"_id": 0})

    if not chofer:
        chofer = await db.choferes_linea.find_one({"email": user["email"]}, {"_id": 0})

    if not chofer:
        raise HTTPException(status_code=404, detail="No eres un chofer registrado")

    # Verificar asignación
    asignacion = await db.asignaciones_ruta.find_one(
        {"chofer_id": chofer["chofer_id"], "status": "active"}, {"_id": 0}
    )

    if not asignacion:
        raise HTTPException(status_code=404, detail="No tienes una ruta asignada")

    # Verificar que no haya otro recorrido activo
    recorrido_existente = await db.recorridos_activos.find_one(
        {"chofer_id": chofer["chofer_id"]}
    )

    if recorrido_existente:
        raise HTTPException(status_code=400, detail="Ya tienes un recorrido activo")

    recorrido_id = f"rec_{uuid.uuid4().hex[:12]}"

    # Datos del QR (lo que escaneará el cliente)
    qr_data = json.dumps(
        {
            "type": "omni_pasaje",
            "recorrido_id": recorrido_id,
            "ruta_id": asignacion["ruta_id"],
            "ruta_codigo": asignacion["ruta_codigo"],
            "tarifa": asignacion["tarifa"],
            "chofer_id": chofer["chofer_id"],
            "vehiculo_placa": asignacion["vehiculo_placa"],
            "linea_id": asignacion["linea_id"],
        }
    )

    now = datetime.now(timezone.utc).isoformat()

    recorrido_doc = {
        "recorrido_id": recorrido_id,
        "ruta_id": asignacion["ruta_id"],
        "ruta_nombre": asignacion["ruta_nombre"],
        "ruta_codigo": asignacion["ruta_codigo"],
        "chofer_id": chofer["chofer_id"],
        "chofer_nombre": chofer["nombre"],
        "vehiculo_id": asignacion["vehiculo_id"],
        "vehiculo_placa": asignacion["vehiculo_placa"],
        "linea_id": asignacion["linea_id"],
        "tarifa": asignacion["tarifa"],
        # Geolocalización
        "lat": lat,
        "lng": lng,
        "heading": None,
        "speed": None,
        # QR
        "qr_data": qr_data,
        # Stats del día
        "pasajeros_hoy": 0,
        "ingresos_hoy": float(0),
        "iniciado_at": now,
        "ultima_actualizacion": now,
    }

    await db.recorridos_activos.insert_one(recorrido_doc)

    if "_id" in recorrido_doc:
        del recorrido_doc["_id"]

    return {
        "message": "Recorrido iniciado",
        "recorrido": recorrido_doc,
        "qr_data": qr_data,
    }


@router.post("/actualizar-ubicacion")
async def actualizar_ubicacion(data: GeoUpdate, user: dict = Depends(get_current_user)):
    """Actualizar la ubicación del chofer en tiempo real"""
    # Buscar chofer
    chofer = await db.choferes_linea.find_one({"user_id": user["user_id"]}, {"_id": 0})

    if not chofer:
        chofer = await db.choferes_linea.find_one({"email": user["email"]}, {"_id": 0})

    if not chofer:
        raise HTTPException(status_code=404, detail="No eres un chofer registrado")

    # Actualizar recorrido activo
    result = await db.recorridos_activos.update_one(
        {"chofer_id": chofer["chofer_id"]},
        {
            "$set": {
                "lat": data.lat,
                "lng": data.lng,
                "heading": data.heading,
                "speed": data.speed,
                "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="No tienes un recorrido activo")

    return {"message": "Ubicación actualizada"}


@router.post("/finalizar-recorrido")
async def finalizar_recorrido(user: dict = Depends(get_current_user)):
    """Finalizar el recorrido activo del chofer"""
    chofer = await db.choferes_linea.find_one({"user_id": user["user_id"]}, {"_id": 0})

    if not chofer:
        chofer = await db.choferes_linea.find_one({"email": user["email"]}, {"_id": 0})

    if not chofer:
        raise HTTPException(status_code=404, detail="No eres un chofer registrado")

    # Obtener recorrido
    recorrido = await db.recorridos_activos.find_one(
        {"chofer_id": chofer["chofer_id"]}, {"_id": 0}
    )

    if not recorrido:
        raise HTTPException(status_code=404, detail="No tienes un recorrido activo")

    # Guardar en histórico
    recorrido["finalizado_at"] = datetime.now(timezone.utc).isoformat()
    await db.recorridos_historico.insert_one(recorrido)

    # Eliminar recorrido activo
    await db.recorridos_activos.delete_one({"chofer_id": chofer["chofer_id"]})

    return {
        "message": "Recorrido finalizado",
        "pasajeros_hoy": recorrido["pasajeros_hoy"],
        "ingresos_hoy": recorrido["ingresos_hoy"],
    }


# ==================== PANEL DEL CLIENTE (MAPA EN VIVO) ====================


@router.get("/rutas-publicas")
async def get_rutas_publicas():
    """Obtener todas las rutas urbanas activas (público)"""
    rutas = await db.rutas_urbanas.find({"status": "active"}, {"_id": 0}).to_list(100)

    return rutas


@router.get("/busetas-activas")
async def get_busetas_activas(ruta_id: Optional[str] = None):
    """Obtener las busetas activas con su ubicación (público)"""
    query = {}
    if ruta_id:
        query["ruta_id"] = ruta_id

    recorridos = await db.recorridos_activos.find(query, {"_id": 0}).to_list(100)

    return recorridos


@router.get("/busetas-activas/{ruta_id}")
async def get_busetas_por_ruta(ruta_id: str):
    """Obtener busetas activas de una ruta específica"""
    recorridos = await db.recorridos_activos.find(
        {"ruta_id": ruta_id}, {"_id": 0}
    ).to_list(50)

    return recorridos


# ==================== MICROPAGOS QR ====================


@router.post("/pagar-pasaje")
async def pagar_pasaje(request: Request, user: dict = Depends(get_current_user)):
    """
    Procesar el pago del pasaje escaneando el QR.

    Modelo de negocio:
    - Tarifa completa se cobra del cliente
    - OMNI retiene fee fijo ($0.02)
    - Línea recibe el resto
    """
    body = await request.json()
    qr_data_str = body.get("qr_data")

    if not qr_data_str:
        raise HTTPException(status_code=400, detail="QR data es requerido")

    # Parsear QR
    try:
        qr_data = json.loads(qr_data_str)
    except:
        raise HTTPException(status_code=400, detail="QR inválido")

    if qr_data.get("type") != "omni_pasaje":
        raise HTTPException(
            status_code=400, detail="Este QR no es válido para pagar pasajes"
        )

    recorrido_id = qr_data.get("recorrido_id")
    ruta_id = qr_data.get("ruta_id")
    tarifa = qr_data.get("tarifa", 0)
    chofer_id = qr_data.get("chofer_id")
    linea_id = qr_data.get("linea_id")

    # Verificar que el recorrido está activo
    recorrido = await db.recorridos_activos.find_one(
        {"recorrido_id": recorrido_id}, {"_id": 0}
    )

    if not recorrido:
        raise HTTPException(status_code=400, detail="Este recorrido ya no está activo")

    # Verificar saldo del cliente
    cliente = await db.users.find_one(
        {"user_id": user["user_id"]}, {"_id": 0, "wallet_balance": 1}
    )

    if not cliente or cliente.get("wallet_balance", 0) < tarifa:
        raise HTTPException(
            status_code=400,
            detail=f"Saldo insuficiente. Necesitas ${tarifa:.2f} y tienes ${cliente.get('wallet_balance', 0):.2f}",
        )

    # Calcular distribución - obtener fee desde configuración admin
    fee_omni = await get_urban_fee()
    monto_linea = tarifa - fee_omni

    # Descontar del cliente
    await db.users.update_one(
        {"user_id": user["user_id"]}, {"$inc": {"wallet_balance": -tarifa}}
    )

    # Acreditar a la línea
    await db.lineas_transporte.update_one(
        {"linea_id": linea_id}, {"$inc": {"wallet_balance": monto_linea}}
    )

    # Actualizar estadísticas del recorrido
    await db.recorridos_activos.update_one(
        {"recorrido_id": recorrido_id},
        {"$inc": {"pasajeros_hoy": 1, "ingresos_hoy": monto_linea}},
    )

    # Actualizar estadísticas de la ruta
    await db.rutas_urbanas.update_one(
        {"ruta_id": ruta_id},
        {
            "$inc": {
                "total_pasajes_hoy": 1,
                "total_ingresos_hoy": monto_linea,
                "total_pasajes_historico": 1,
                "total_ingresos_historico": monto_linea,
            }
        },
    )

    # Registrar transacción
    pago_id = f"pago_{uuid.uuid4().hex[:12]}"
    pago_doc = {
        "pago_id": pago_id,
        "recorrido_id": recorrido_id,
        "ruta_id": ruta_id,
        "ruta_codigo": qr_data.get("ruta_codigo"),
        "vehiculo_placa": qr_data.get("vehiculo_placa"),
        "chofer_id": chofer_id,
        "linea_id": linea_id,
        "user_id": user["user_id"],
        "user_email": user.get("email"),
        "tarifa": tarifa,
        "fee_omni": fee_omni,
        "monto_linea": monto_linea,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.micropagos_qr.insert_one(pago_doc)

    # Obtener nuevo saldo
    cliente_actualizado = await db.users.find_one(
        {"user_id": user["user_id"]}, {"_id": 0, "wallet_balance": 1}
    )

    return {
        "message": "¡Pasaje pagado exitosamente!",
        "pago_id": pago_id,
        "detalles": {
            "ruta": recorrido["ruta_nombre"],
            "vehiculo": recorrido["vehiculo_placa"],
            "tarifa_pagada": tarifa,
            "nuevo_saldo": cliente_actualizado.get("wallet_balance", 0),
        },
    }


@router.get("/mis-pasajes")
async def get_mis_pasajes(user: dict = Depends(get_current_user)):
    """Obtener historial de pasajes pagados por el cliente"""
    pasajes = (
        await db.micropagos_qr.find({"user_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .limit(50)
        .to_list(50)
    )

    return pasajes

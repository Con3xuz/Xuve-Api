"""
Rutas para el Sistema de Líneas de Transporte Urbano

Este módulo implementa la gestión de:
- Líneas de Transporte Urbano (rol: urban_line_admin)
- Rutas urbanas con trazado en mapa
- Flotas y choferes de líneas urbanas
- Geolocalización y micropagos QR

Separado del sistema de Terminales Interurbanos (line_admin).
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import json

from utils.database import db
from utils.auth import get_current_user
from utils.financial_config import get_urban_fee
from models.urban_line_models import (
    UrbanLineCreate,
    UrbanVehiculoCreate,
    UrbanChoferCreate,
    UrbanRutaCreate,
    UrbanAsignacionCreate,
    UrbanGeoUpdate,
)

router = APIRouter(prefix="/urban-linea", tags=["Líneas Transporte Urbano"])


# ==================== HELPERS ====================


async def get_urban_linea_by_admin(user_id: str):
    """Obtener la línea urbana administrada por un usuario"""
    linea = await db.lineas_urbanas.find_one({"admin_user_id": user_id}, {"_id": 0})
    return linea


async def verify_urban_line_admin(user: dict):
    """Verificar que el usuario es urban_line_admin"""
    if user["role"] != "urban_line_admin" and user["role"] != "admin":
        raise HTTPException(
            status_code=403, detail="Acceso denegado. Se requiere rol urban_line_admin"
        )

    linea = await get_urban_linea_by_admin(user["user_id"])
    if not linea:
        raise HTTPException(
            status_code=404, detail="No tienes una línea urbana registrada"
        )

    return linea


# ==================== GESTIÓN DE LÍNEA URBANA ====================


@router.post("/registro")
async def registrar_linea_urbana(
    data: UrbanLineCreate, user: dict = Depends(get_current_user)
):
    """
    Registrar una nueva Línea de Transporte Urbano.
    El usuario se convierte en urban_line_admin.
    """
    # Verificar que no tenga ya una línea
    existing = await get_urban_linea_by_admin(user["user_id"])
    if existing:
        raise HTTPException(status_code=400, detail="Ya administras una línea urbana")

    # Verificar RIF único
    rif_exists = await db.lineas_urbanas.find_one({"rif": data.rif}, {"_id": 0})
    if rif_exists:
        raise HTTPException(status_code=400, detail="Este RIF ya está registrado")

    linea_id = f"urban_{uuid.uuid4().hex[:12]}"

    linea_doc = {
        "linea_id": linea_id,
        "admin_user_id": user["user_id"],
        "nombre_linea": data.nombre_linea,
        "rif": data.rif,
        "direccion_oficina": data.direccion_oficina,
        "telefono_contacto": data.telefono_contacto,
        "email_contacto": data.email_contacto,
        "zona_operacion": data.zona_operacion,
        "descripcion": data.descripcion,
        "logo_url": data.logo_url,
        # Billetera
        "wallet_balance": 0.0,
        # Estado
        "status": "pending_kyc",
        # Stats
        "total_pasajes": 0,
        "total_ingresos": 0.0,
        "avg_rating": 5.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.lineas_urbanas.insert_one(linea_doc)

    # Actualizar rol del usuario
    await db.users.update_one(
        {"user_id": user["user_id"]}, {"$set": {"role": "urban_line_admin"}}
    )

    if "_id" in linea_doc:
        del linea_doc["_id"]

    return {
        "message": "Línea urbana registrada. Pendiente de aprobación.",
        "linea": linea_doc,
    }


@router.get("/mi-linea")
async def get_mi_linea_urbana(user: dict = Depends(get_current_user)):
    """Obtener información de mi línea urbana"""
    linea = await verify_urban_line_admin(user)

    # Contar vehículos y choferes
    vehiculos_count = await db.vehiculos_urbanos.count_documents(
        {"linea_id": linea["linea_id"]}
    )
    choferes_count = await db.choferes_urbanos.count_documents(
        {"linea_id": linea["linea_id"]}
    )
    rutas_count = await db.rutas_urbanas_v2.count_documents(
        {"linea_id": linea["linea_id"]}
    )

    linea["vehiculos_count"] = vehiculos_count
    linea["choferes_count"] = choferes_count
    linea["rutas_count"] = rutas_count

    return linea


@router.post("/recargar")
async def recargar_wallet_urbana(
    request: Request, user: dict = Depends(get_current_user)
):
    """Recargar la billetera de la Línea Urbana"""
    linea = await verify_urban_line_admin(user)
    body = await request.json()
    monto = body.get("monto", 0)

    if monto <= 0:
        raise HTTPException(status_code=400, detail="Monto inválido")

    await db.lineas_urbanas.update_one(
        {"linea_id": linea["linea_id"]}, {"$inc": {"wallet_balance": monto}}
    )

    # Registrar transacción
    await db.transactions.insert_one(
        {
            "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
            "entity_type": "linea_urbana",
            "entity_id": linea["linea_id"],
            "amount_usd": monto,
            "type": "RECHARGE",
            "status": "completed",
            "description": f"Recarga billetera - {linea['nombre_linea']}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    updated = await db.lineas_urbanas.find_one(
        {"linea_id": linea["linea_id"]}, {"_id": 0, "wallet_balance": 1}
    )

    return {
        "message": f"Recarga de ${monto:.2f} exitosa",
        "nuevo_saldo": updated["wallet_balance"],
    }


# ==================== GESTIÓN DE VEHÍCULOS ====================


@router.post("/vehiculos")
async def registrar_vehiculo_urbano(
    data: UrbanVehiculoCreate, user: dict = Depends(get_current_user)
):
    """Registrar un vehículo en la flota urbana"""
    linea = await verify_urban_line_admin(user)

    # Verificar placa única
    existing = await db.vehiculos_urbanos.find_one(
        {"linea_id": linea["linea_id"], "placa": data.placa.upper()}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya existe un vehículo con esta placa"
        )

    vehiculo_id = f"vurb_{uuid.uuid4().hex[:12]}"

    vehiculo_doc = {
        "vehiculo_id": vehiculo_id,
        "linea_id": linea["linea_id"],
        "placa": data.placa.upper(),
        "marca": data.marca,
        "modelo": data.modelo,
        "year": data.year,
        "capacidad_pasajeros": data.capacidad_pasajeros,
        "tipo_vehiculo": data.tipo_vehiculo,
        "foto_url": data.foto_url,
        "circulation_card_url": data.circulation_card_url,
        "rcv_insurance_url": data.rcv_insurance_url,
        "status": "active",
        "ruta_asignada_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.vehiculos_urbanos.insert_one(vehiculo_doc)

    if "_id" in vehiculo_doc:
        del vehiculo_doc["_id"]

    return {"message": "Vehículo registrado", "vehiculo": vehiculo_doc}


@router.get("/vehiculos")
async def listar_vehiculos_urbanos(user: dict = Depends(get_current_user)):
    """Listar vehículos de mi línea urbana"""
    linea = await verify_urban_line_admin(user)

    vehiculos = await db.vehiculos_urbanos.find(
        {"linea_id": linea["linea_id"]}, {"_id": 0}
    ).to_list(100)

    return vehiculos


@router.delete("/vehiculos/{vehiculo_id}")
async def eliminar_vehiculo_urbano(
    vehiculo_id: str, user: dict = Depends(get_current_user)
):
    """Eliminar un vehículo de la flota"""
    linea = await verify_urban_line_admin(user)

    result = await db.vehiculos_urbanos.delete_one(
        {"vehiculo_id": vehiculo_id, "linea_id": linea["linea_id"]}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    return {"message": "Vehículo eliminado"}


# ==================== GESTIÓN DE CHOFERES ====================


@router.post("/choferes")
async def registrar_chofer_urbano(
    data: UrbanChoferCreate, user: dict = Depends(get_current_user)
):
    """
    Registrar un chofer de línea urbana.
    Requiere licencia de 5ta grado.
    """
    linea = await verify_urban_line_admin(user)

    # Validar licencia de 5ta grado
    if data.licencia_categoria != "5ta":
        raise HTTPException(
            status_code=400,
            detail="Los choferes de línea urbana deben tener licencia de 5ta grado",
        )

    # Verificar cédula única
    existing = await db.choferes_urbanos.find_one(
        {"linea_id": linea["linea_id"], "cedula": data.cedula}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya existe un chofer con esta cédula"
        )

    chofer_id = f"churb_{uuid.uuid4().hex[:12]}"

    chofer_doc = {
        "chofer_id": chofer_id,
        "linea_id": linea["linea_id"],
        "user_id": None,  # Se puede vincular después
        "nombre": data.nombre,
        "cedula": data.cedula,
        "telefono": data.telefono,
        "email": data.email,
        # Documentos
        "cedula_url": data.cedula_url,
        "licencia_url": data.licencia_url,
        "licencia_categoria": data.licencia_categoria,
        "medical_card_url": data.medical_card_url,
        "medical_card_expiry": data.medical_card_expiry,
        "foto_url": data.foto_url,
        "antecedentes_url": data.antecedentes_url,
        "status": "active",
        "total_recorridos": 0,
        "total_pasajeros": 0,
        "avg_rating": 5.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.choferes_urbanos.insert_one(chofer_doc)

    if "_id" in chofer_doc:
        del chofer_doc["_id"]

    return {"message": "Chofer registrado", "chofer": chofer_doc}


@router.get("/choferes")
async def listar_choferes_urbanos(user: dict = Depends(get_current_user)):
    """Listar choferes de mi línea urbana"""
    linea = await verify_urban_line_admin(user)

    choferes = await db.choferes_urbanos.find(
        {"linea_id": linea["linea_id"]}, {"_id": 0}
    ).to_list(100)

    return choferes


@router.delete("/choferes/{chofer_id}")
async def eliminar_chofer_urbano(
    chofer_id: str, user: dict = Depends(get_current_user)
):
    """Eliminar un chofer de la línea"""
    linea = await verify_urban_line_admin(user)

    result = await db.choferes_urbanos.delete_one(
        {"chofer_id": chofer_id, "linea_id": linea["linea_id"]}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Chofer no encontrado")

    return {"message": "Chofer eliminado"}


# ==================== GESTIÓN DE RUTAS ====================


@router.post("/rutas")
async def crear_ruta_urbana(
    data: UrbanRutaCreate, user: dict = Depends(get_current_user)
):
    """Crear una nueva ruta urbana con trazado en mapa"""
    linea = await verify_urban_line_admin(user)

    # Verificar código único
    existing = await db.rutas_urbanas_v2.find_one(
        {"linea_id": linea["linea_id"], "codigo_ruta": data.codigo_ruta.upper()}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya existe una ruta con este código"
        )

    ruta_id = f"rurb_{uuid.uuid4().hex[:12]}"

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
        "color": data.color,
        # Trazado de la ruta
        "waypoints": data.waypoints or [],
        # Asignaciones
        "asignaciones": [],
        # Estadísticas
        "total_pasajes_hoy": 0,
        "total_ingresos_hoy": 0.0,
        "total_pasajes_historico": 0,
        "total_ingresos_historico": 0.0,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.rutas_urbanas_v2.insert_one(ruta_doc)

    if "_id" in ruta_doc:
        del ruta_doc["_id"]

    return {"message": "Ruta creada", "ruta": ruta_doc}


@router.get("/rutas")
async def listar_rutas_urbanas(user: dict = Depends(get_current_user)):
    """Listar rutas de mi línea urbana"""
    linea = await verify_urban_line_admin(user)

    rutas = await db.rutas_urbanas_v2.find(
        {"linea_id": linea["linea_id"]}, {"_id": 0}
    ).to_list(50)

    return rutas


@router.delete("/rutas/{ruta_id}")
async def eliminar_ruta_urbana(ruta_id: str, user: dict = Depends(get_current_user)):
    """Eliminar una ruta urbana"""
    linea = await verify_urban_line_admin(user)

    # Verificar que no haya recorridos activos
    recorrido_activo = await db.recorridos_urbanos.find_one({"ruta_id": ruta_id})
    if recorrido_activo:
        raise HTTPException(
            status_code=400, detail="No puedes eliminar una ruta con recorridos activos"
        )

    result = await db.rutas_urbanas_v2.delete_one(
        {"ruta_id": ruta_id, "linea_id": linea["linea_id"]}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    # Eliminar asignaciones
    await db.asignaciones_urbanas.delete_many({"ruta_id": ruta_id})

    return {"message": "Ruta eliminada"}


@router.put("/rutas/{ruta_id}/waypoints")
async def actualizar_waypoints(
    ruta_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """Actualizar el trazado de la ruta (waypoints)"""
    linea = await verify_urban_line_admin(user)
    body = await request.json()
    waypoints = body.get("waypoints", [])

    result = await db.rutas_urbanas_v2.update_one(
        {"ruta_id": ruta_id, "linea_id": linea["linea_id"]},
        {"$set": {"waypoints": waypoints}},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    return {"message": "Trazado actualizado"}


@router.post("/rutas/{ruta_id}/asignar")
async def asignar_a_ruta_urbana(
    ruta_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """Asignar un chofer y vehículo a una ruta"""
    linea = await verify_urban_line_admin(user)
    body = await request.json()

    chofer_id = body.get("chofer_id")
    vehiculo_id = body.get("vehiculo_id")

    if not chofer_id or not vehiculo_id:
        raise HTTPException(
            status_code=400, detail="chofer_id y vehiculo_id son requeridos"
        )

    # Verificar ruta
    ruta = await db.rutas_urbanas_v2.find_one(
        {"ruta_id": ruta_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    # Verificar chofer
    chofer = await db.choferes_urbanos.find_one(
        {"chofer_id": chofer_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not chofer:
        raise HTTPException(status_code=404, detail="Chofer no encontrado")

    # Verificar vehículo
    vehiculo = await db.vehiculos_urbanos.find_one(
        {"vehiculo_id": vehiculo_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    # Verificar que no esté ya asignado a otra ruta activa
    asignacion_existente = await db.asignaciones_urbanas.find_one(
        {"chofer_id": chofer_id, "status": "active"}
    )

    if asignacion_existente and asignacion_existente["ruta_id"] != ruta_id:
        raise HTTPException(
            status_code=400,
            detail=f"Este chofer ya está asignado a la ruta {asignacion_existente['ruta_codigo']}",
        )

    asignacion_id = f"asurb_{uuid.uuid4().hex[:12]}"

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

    # Upsert
    await db.asignaciones_urbanas.update_one(
        {"chofer_id": chofer_id, "ruta_id": ruta_id},
        {"$set": asignacion_doc},
        upsert=True,
    )

    # Actualizar lista en la ruta
    nueva_asignacion = {
        "chofer_id": chofer_id,
        "chofer_nombre": chofer["nombre"],
        "vehiculo_id": vehiculo_id,
        "vehiculo_placa": vehiculo["placa"],
    }

    asignaciones_actuales = ruta.get("asignaciones", [])
    ya_existe = any(a["chofer_id"] == chofer_id for a in asignaciones_actuales)

    if not ya_existe:
        await db.rutas_urbanas_v2.update_one(
            {"ruta_id": ruta_id}, {"$push": {"asignaciones": nueva_asignacion}}
        )

    return {"message": f"Chofer {chofer['nombre']} asignado a {ruta['nombre_ruta']}"}


@router.delete("/rutas/{ruta_id}/asignar/{chofer_id}")
async def desasignar_de_ruta_urbana(
    ruta_id: str, chofer_id: str, user: dict = Depends(get_current_user)
):
    """Desasignar un chofer de una ruta"""
    await verify_urban_line_admin(user)  # Only verify access

    # Verificar que no tenga recorrido activo
    recorrido = await db.recorridos_urbanos.find_one(
        {"ruta_id": ruta_id, "chofer_id": chofer_id}
    )

    if recorrido:
        raise HTTPException(
            status_code=400,
            detail="No puedes desasignar un chofer con recorrido activo",
        )

    # Eliminar asignación
    await db.asignaciones_urbanas.delete_one(
        {"ruta_id": ruta_id, "chofer_id": chofer_id}
    )

    # Actualizar ruta
    await db.rutas_urbanas_v2.update_one(
        {"ruta_id": ruta_id}, {"$pull": {"asignaciones": {"chofer_id": chofer_id}}}
    )

    return {"message": "Chofer desasignado de la ruta"}


# ==================== PANEL DEL CHOFER URBANO ====================


@router.get("/chofer/mi-asignacion")
async def get_mi_asignacion_urbana(user: dict = Depends(get_current_user)):
    """Obtener la asignación del chofer actual"""
    # Buscar chofer por user_id o email
    chofer = await db.choferes_urbanos.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )

    if not chofer:
        chofer = await db.choferes_urbanos.find_one(
            {"email": user["email"]}, {"_id": 0}
        )

    if not chofer:
        raise HTTPException(
            status_code=404, detail="No estás registrado como chofer urbano"
        )

    # Buscar asignación activa
    asignacion = await db.asignaciones_urbanas.find_one(
        {"chofer_id": chofer["chofer_id"], "status": "active"}, {"_id": 0}
    )

    # Buscar recorrido activo
    recorrido = await db.recorridos_urbanos.find_one(
        {"chofer_id": chofer["chofer_id"]}, {"_id": 0}
    )

    return {"asignacion": asignacion, "chofer": chofer, "recorrido_activo": recorrido}


@router.post("/chofer/iniciar-recorrido")
async def iniciar_recorrido_urbano(
    request: Request, user: dict = Depends(get_current_user)
):
    """Iniciar un recorrido en una ruta urbana"""
    body = await request.json()
    lat = body.get("lat", 0)
    lng = body.get("lng", 0)

    # Buscar chofer
    chofer = await db.choferes_urbanos.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )

    if not chofer:
        chofer = await db.choferes_urbanos.find_one(
            {"email": user["email"]}, {"_id": 0}
        )

    if not chofer:
        raise HTTPException(status_code=404, detail="No eres un chofer registrado")

    # Verificar asignación
    asignacion = await db.asignaciones_urbanas.find_one(
        {"chofer_id": chofer["chofer_id"], "status": "active"}, {"_id": 0}
    )

    if not asignacion:
        raise HTTPException(status_code=404, detail="No tienes una ruta asignada")

    # Verificar que no haya otro recorrido activo
    recorrido_existente = await db.recorridos_urbanos.find_one(
        {"chofer_id": chofer["chofer_id"]}
    )

    if recorrido_existente:
        raise HTTPException(status_code=400, detail="Ya tienes un recorrido activo")

    recorrido_id = f"recurb_{uuid.uuid4().hex[:12]}"

    # Datos del QR
    qr_data = json.dumps(
        {
            "type": "xuve_pasaje_urbano",
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
        "ingresos_hoy": 0.0,
        "iniciado_at": now,
        "ultima_actualizacion": now,
    }

    await db.recorridos_urbanos.insert_one(recorrido_doc)

    if "_id" in recorrido_doc:
        del recorrido_doc["_id"]

    return {
        "message": "Recorrido iniciado",
        "recorrido": recorrido_doc,
        "qr_data": qr_data,
    }


@router.post("/chofer/actualizar-ubicacion")
async def actualizar_ubicacion_urbana(
    data: UrbanGeoUpdate, user: dict = Depends(get_current_user)
):
    """Actualizar la ubicación del chofer"""
    chofer = await db.choferes_urbanos.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )

    if not chofer:
        chofer = await db.choferes_urbanos.find_one(
            {"email": user["email"]}, {"_id": 0}
        )

    if not chofer:
        raise HTTPException(status_code=404, detail="No eres un chofer registrado")

    result = await db.recorridos_urbanos.update_one(
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


@router.post("/chofer/finalizar-recorrido")
async def finalizar_recorrido_urbano(user: dict = Depends(get_current_user)):
    """Finalizar el recorrido activo"""
    chofer = await db.choferes_urbanos.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )

    if not chofer:
        chofer = await db.choferes_urbanos.find_one(
            {"email": user["email"]}, {"_id": 0}
        )

    if not chofer:
        raise HTTPException(status_code=404, detail="No eres un chofer registrado")

    recorrido = await db.recorridos_urbanos.find_one(
        {"chofer_id": chofer["chofer_id"]}, {"_id": 0}
    )

    if not recorrido:
        raise HTTPException(status_code=404, detail="No tienes un recorrido activo")

    # Guardar en histórico
    recorrido["finalizado_at"] = datetime.now(timezone.utc).isoformat()
    await db.recorridos_urbanos_historico.insert_one(recorrido)

    # Actualizar stats del chofer
    await db.choferes_urbanos.update_one(
        {"chofer_id": chofer["chofer_id"]},
        {
            "$inc": {
                "total_recorridos": 1,
                "total_pasajeros": recorrido["pasajeros_hoy"],
            }
        },
    )

    # Eliminar recorrido activo
    await db.recorridos_urbanos.delete_one({"chofer_id": chofer["chofer_id"]})

    return {
        "message": "Recorrido finalizado",
        "pasajeros_hoy": recorrido["pasajeros_hoy"],
        "ingresos_hoy": recorrido["ingresos_hoy"],
    }


# ==================== ENDPOINTS PÚBLICOS ====================


@router.get("/publico/rutas")
async def get_rutas_publicas_urbanas(zona: Optional[str] = None):
    """Obtener rutas urbanas públicas"""
    query = {"status": "active"}

    rutas = await db.rutas_urbanas_v2.find(query, {"_id": 0}).to_list(100)

    return rutas


@router.get("/publico/busetas-activas")
async def get_busetas_activas_urbanas(ruta_id: Optional[str] = None):
    """Obtener busetas activas con ubicación"""
    query = {}
    if ruta_id:
        query["ruta_id"] = ruta_id

    recorridos = await db.recorridos_urbanos.find(query, {"_id": 0}).to_list(100)

    return recorridos


@router.post("/publico/pagar-pasaje")
async def pagar_pasaje_urbano(request: Request, user: dict = Depends(get_current_user)):
    """Procesar el pago del pasaje escaneando el QR"""
    body = await request.json()
    qr_data_str = body.get("qr_data")

    if not qr_data_str:
        raise HTTPException(status_code=400, detail="QR data es requerido")

    try:
        qr_data = json.loads(qr_data_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="QR inválido")

    if qr_data.get("type") != "xuve_pasaje_urbano":
        raise HTTPException(
            status_code=400, detail="Este QR no es válido para pasajes urbanos"
        )

    recorrido_id = qr_data.get("recorrido_id")
    ruta_id = qr_data.get("ruta_id")
    tarifa = qr_data.get("tarifa", 0)
    chofer_id = qr_data.get("chofer_id")
    linea_id = qr_data.get("linea_id")

    # Verificar recorrido activo
    recorrido = await db.recorridos_urbanos.find_one(
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
            status_code=400, detail=f"Saldo insuficiente. Necesitas ${tarifa:.2f}"
        )

    # Calcular distribución - obtener fee desde configuración admin
    fee_xuve = await get_urban_fee()
    monto_linea = tarifa - fee_xuve

    # Descontar del cliente
    await db.users.update_one(
        {"user_id": user["user_id"]}, {"$inc": {"wallet_balance": -tarifa}}
    )

    # Acreditar a la línea
    await db.lineas_urbanas.update_one(
        {"linea_id": linea_id},
        {
            "$inc": {
                "wallet_balance": monto_linea,
                "total_ingresos": monto_linea,
                "total_pasajes": 1,
            }
        },
    )

    # Actualizar estadísticas del recorrido
    await db.recorridos_urbanos.update_one(
        {"recorrido_id": recorrido_id},
        {"$inc": {"pasajeros_hoy": 1, "ingresos_hoy": monto_linea}},
    )

    # Actualizar estadísticas de la ruta
    await db.rutas_urbanas_v2.update_one(
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
    pago_id = f"purb_{uuid.uuid4().hex[:12]}"
    await db.micropagos_urbanos.insert_one(
        {
            "pago_id": pago_id,
            "recorrido_id": recorrido_id,
            "ruta_id": ruta_id,
            "ruta_codigo": qr_data.get("ruta_codigo"),
            "vehiculo_placa": qr_data.get("vehiculo_placa"),
            "chofer_id": chofer_id,
            "linea_id": linea_id,
            "user_id": user["user_id"],
            "tarifa": tarifa,
            "fee_xuve": fee_xuve,
            "monto_linea": monto_linea,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Obtener nuevo saldo
    cliente_actualizado = await db.users.find_one(
        {"user_id": user["user_id"]}, {"_id": 0, "wallet_balance": 1}
    )

    return {
        "message": "¡Pasaje pagado!",
        "pago_id": pago_id,
        "detalles": {
            "ruta": recorrido["ruta_nombre"],
            "vehiculo": recorrido["vehiculo_placa"],
            "tarifa_pagada": tarifa,
            "nuevo_saldo": cliente_actualizado.get("wallet_balance", 0),
        },
    }

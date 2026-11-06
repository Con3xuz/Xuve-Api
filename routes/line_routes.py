"""
Rutas para el Sistema B2B de Líneas de Transporte

Este módulo implementa la gestión de:
- Líneas de Transporte (Terminales) - rol: line_admin
- Flota de Vehículos de la Línea
- Choferes afiliados a la Línea
- Viajes Interurbanos (Terminal Digital)
- Rutas Urbanas (Micropagos QR) - Pendiente

WALLET GUARD: La comisión configurada se cobra de la billetera de la LÍNEA,
no del chofer individual. La Línea prepaga la garantía a Xuve.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional, List
from datetime import datetime, timezone
import uuid

from utils.database import db
from utils.auth import get_current_user
from utils.financial_config import get_commission_rate, get_financial_config
from models.wallet_models import TransactionType
from models.line_models import (
    LineaTransporteCreate,
    VehiculoLineaCreate,
    ChoferLineaCreate,
    ViajeInterurbanoCreate,
    RutaUrbanaCreate,
)

router = APIRouter(prefix="/linea", tags=["Líneas de Transporte B2B"])


# ==================== HELPERS ====================


async def get_linea_by_admin(user_id: str):
    """Obtener la línea administrada por un usuario"""
    linea = await db.lineas_transporte.find_one({"admin_user_id": user_id}, {"_id": 0})
    return linea


async def verify_line_admin(user: dict):
    """Verificar que el usuario es line_admin y tiene línea registrada"""
    if user["role"] != "line_admin" and user["role"] != "admin":
        raise HTTPException(
            status_code=403, detail="Acceso denegado. Se requiere rol line_admin"
        )

    linea = await get_linea_by_admin(user["user_id"])
    if not linea:
        raise HTTPException(
            status_code=404, detail="No tienes una línea de transporte registrada"
        )

    return linea


# ==================== GESTIÓN DE LÍNEA ====================


@router.post("/registro")
async def registrar_linea(
    data: LineaTransporteCreate, user: dict = Depends(get_current_user)
):
    """
    Registrar una nueva Línea de Transporte.
    El usuario actual se convierte en line_admin de esta línea.
    """
    # Verificar que no tenga ya una línea
    existing = await get_linea_by_admin(user["user_id"])
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya administras una línea de transporte"
        )

    # Verificar RIF único
    rif_exists = await db.lineas_transporte.find_one({"rif": data.rif}, {"_id": 0})
    if rif_exists:
        raise HTTPException(status_code=400, detail="Este RIF ya está registrado")

    linea_id = f"linea_{uuid.uuid4().hex[:12]}"

    linea_doc = {
        "linea_id": linea_id,
        "admin_user_id": user["user_id"],
        "nombre_linea": data.nombre_linea,
        "rif": data.rif,
        "direccion_oficina": data.direccion_oficina,
        "telefono_contacto": data.telefono_contacto,
        "email_contacto": data.email_contacto,
        "tipo_servicio": data.tipo_servicio.value,
        "descripcion": data.descripcion,
        "logo_url": data.logo_url,
        # Billetera centralizada
        "wallet_balance": 0.0,
        "wallet_held": 0.0,
        # Estado
        "status": "pending_kyc",
        "activation_fee_paid": False,
        # Stats
        "total_viajes": 0,
        "total_pasajeros": 0,
        "total_earnings": 0.0,
        "avg_rating": 5.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.lineas_transporte.insert_one(linea_doc)

    # Actualizar rol del usuario a line_admin
    await db.users.update_one(
        {"user_id": user["user_id"]}, {"$set": {"role": "line_admin"}}
    )

    if "_id" in linea_doc:
        del linea_doc["_id"]

    return {
        "message": "Línea de transporte registrada. Pendiente de aprobación KYC.",
        "linea": linea_doc,
    }


@router.get("/mi-linea")
async def get_mi_linea(user: dict = Depends(get_current_user)):
    """Obtener información de la línea que administro"""
    linea = await verify_line_admin(user)

    # Contar vehículos y choferes
    vehiculos_count = await db.vehiculos_linea.count_documents(
        {"linea_id": linea["linea_id"]}
    )
    choferes_count = await db.choferes_linea.count_documents(
        {"linea_id": linea["linea_id"]}
    )

    linea["vehiculos_count"] = vehiculos_count
    linea["choferes_count"] = choferes_count

    return linea


@router.post("/recargar")
async def recargar_wallet_linea(
    request: Request, user: dict = Depends(get_current_user)
):
    """Recargar la billetera de la Línea"""
    linea = await verify_line_admin(user)
    body = await request.json()
    monto = body.get("monto", 0)

    if monto <= 0:
        raise HTTPException(status_code=400, detail="Monto inválido")

    await db.lineas_transporte.update_one(
        {"linea_id": linea["linea_id"]}, {"$inc": {"wallet_balance": monto}}
    )

    # Registrar transacción
    await db.transactions.insert_one(
        {
            "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
            "entity_type": "linea",
            "entity_id": linea["linea_id"],
            "amount_usd": monto,
            "type": "RECHARGE",
            "status": "completed",
            "description": f"Recarga billetera - {linea['nombre_linea']}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    updated = await db.lineas_transporte.find_one(
        {"linea_id": linea["linea_id"]}, {"_id": 0, "wallet_balance": 1}
    )

    return {
        "message": f"Recarga de ${monto:.2f} exitosa",
        "nuevo_saldo": updated["wallet_balance"],
    }


# ==================== GESTIÓN DE VEHÍCULOS ====================


@router.post("/vehiculos")
async def registrar_vehiculo(
    data: VehiculoLineaCreate, user: dict = Depends(get_current_user)
):
    """Registrar un vehículo en la flota de la Línea"""
    linea = await verify_line_admin(user)

    # Verificar placa única en la línea
    existing = await db.vehiculos_linea.find_one(
        {"linea_id": linea["linea_id"], "placa": data.placa.upper()}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya existe un vehículo con esta placa"
        )

    vehiculo_id = f"veh_{uuid.uuid4().hex[:12]}"

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
        "qr_code": None,
        "ruta_asignada_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.vehiculos_linea.insert_one(vehiculo_doc)

    if "_id" in vehiculo_doc:
        del vehiculo_doc["_id"]

    return {"message": "Vehículo registrado", "vehiculo": vehiculo_doc}


@router.get("/vehiculos")
async def listar_vehiculos(user: dict = Depends(get_current_user)):
    """Listar vehículos de la flota de mi Línea"""
    linea = await verify_line_admin(user)

    vehiculos = await db.vehiculos_linea.find(
        {"linea_id": linea["linea_id"]}, {"_id": 0}
    ).to_list(100)

    return vehiculos


@router.delete("/vehiculos/{vehiculo_id}")
async def eliminar_vehiculo(vehiculo_id: str, user: dict = Depends(get_current_user)):
    """Eliminar un vehículo de la flota"""
    linea = await verify_line_admin(user)

    result = await db.vehiculos_linea.delete_one(
        {"vehiculo_id": vehiculo_id, "linea_id": linea["linea_id"]}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    return {"message": "Vehículo eliminado"}


# ==================== GESTIÓN DE CHOFERES ====================


@router.post("/choferes")
async def registrar_chofer(
    data: ChoferLineaCreate, user: dict = Depends(get_current_user)
):
    """
    Registrar un chofer afiliado a la Línea.
    Requiere los mismos documentos que un conductor de taxi.
    OBLIGATORIO: Licencia de 5ta grado.
    """
    linea = await verify_line_admin(user)

    # Validar licencia de 5ta grado
    if data.licencia_categoria != "5ta":
        raise HTTPException(
            status_code=400,
            detail="Los choferes de línea de transporte deben tener licencia de 5ta grado",
        )

    # Verificar cédula única en la línea
    existing = await db.choferes_linea.find_one(
        {"linea_id": linea["linea_id"], "cedula": data.cedula}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Ya existe un chofer con esta cédula"
        )

    chofer_id = f"chofer_{uuid.uuid4().hex[:12]}"

    chofer_doc = {
        "chofer_id": chofer_id,
        "linea_id": linea["linea_id"],
        "user_id": None,  # Se puede vincular después a una cuenta Xuve
        "nombre": data.nombre,
        "cedula": data.cedula,
        "telefono": data.telefono,
        "email": data.email,
        # Documentos obligatorios
        "cedula_url": data.cedula_url,
        "licencia_url": data.licencia_url,
        "licencia_categoria": data.licencia_categoria,
        "medical_card_url": data.medical_card_url,
        "medical_card_expiry": data.medical_card_expiry,
        "foto_url": data.foto_url,
        "antecedentes_url": data.antecedentes_url,
        "status": "active",
        "total_viajes": 0,
        "avg_rating": 5.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.choferes_linea.insert_one(chofer_doc)

    if "_id" in chofer_doc:
        del chofer_doc["_id"]

    return {"message": "Chofer registrado exitosamente", "chofer": chofer_doc}


@router.get("/choferes")
async def listar_choferes(user: dict = Depends(get_current_user)):
    """Listar choferes afiliados a mi Línea"""
    linea = await verify_line_admin(user)

    choferes = await db.choferes_linea.find(
        {"linea_id": linea["linea_id"]}, {"_id": 0}
    ).to_list(100)

    return choferes


@router.delete("/choferes/{chofer_id}")
async def eliminar_chofer(chofer_id: str, user: dict = Depends(get_current_user)):
    """Eliminar un chofer de la Línea"""
    linea = await verify_line_admin(user)

    result = await db.choferes_linea.delete_one(
        {"chofer_id": chofer_id, "linea_id": linea["linea_id"]}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Chofer no encontrado")

    return {"message": "Chofer eliminado"}


# ==================== TERMINAL DIGITAL: VIAJES INTERURBANOS ====================


@router.post("/viajes")
async def crear_viaje(
    data: ViajeInterurbanoCreate, user: dict = Depends(get_current_user)
):
    """
    Crear un viaje programado (Terminal Digital).

    WALLET GUARD: La Línea debe tener saldo >= 10% del ingreso potencial.
    La comisión se cobra de la billetera de la LÍNEA.
    """
    linea = await verify_line_admin(user)

    if linea["status"] != "approved":
        raise HTTPException(
            status_code=403, detail="Tu línea debe estar aprobada para publicar viajes"
        )

    # Verificar que el vehículo pertenece a la línea
    vehiculo = await db.vehiculos_linea.find_one(
        {"vehiculo_id": data.vehiculo_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not vehiculo:
        raise HTTPException(
            status_code=404, detail="Vehículo no encontrado en tu flota"
        )

    if vehiculo["status"] != "active":
        raise HTTPException(status_code=400, detail="Este vehículo no está activo")

    # Verificar chofer si se asigna
    chofer_info = None
    if data.chofer_id:
        chofer = await db.choferes_linea.find_one(
            {"chofer_id": data.chofer_id, "linea_id": linea["linea_id"]}, {"_id": 0}
        )

        if not chofer:
            raise HTTPException(
                status_code=404, detail="Chofer no encontrado en tu línea"
            )

        chofer_info = {
            "chofer_id": chofer["chofer_id"],
            "nombre": chofer["nombre"],
            "telefono": chofer["telefono"],
        }

    # Validar capacidad de puestos (mínimo 1, máximo razonable)
    capacidad = data.capacidad_puestos
    if capacidad < 1:
        raise HTTPException(
            status_code=400, detail="La capacidad debe ser al menos 1 puesto"
        )
    if capacidad > 100:
        raise HTTPException(
            status_code=400, detail="La capacidad máxima es de 100 puestos"
        )

    # Obtener tasa de comisión desde la configuración del admin
    commission_rate = await get_commission_rate("linea")

    # WALLET GUARD: Calcular comisión potencial máxima
    ingreso_potencial = data.precio_asiento * capacidad
    comision_maxima = ingreso_potencial * commission_rate

    # Verificar saldo de la LÍNEA (no del usuario)
    available_balance = linea["wallet_balance"] - linea.get("wallet_held", 0)

    if available_balance < comision_maxima:
        raise HTTPException(
            status_code=403,
            detail=f"Saldo insuficiente de la Línea. Necesitas ${comision_maxima:.2f} "
            f"({int(commission_rate*100)}% de ${ingreso_potencial:.2f}) para garantizar este viaje. "
            f"Saldo disponible: ${available_balance:.2f}",
        )

    viaje_id = f"viaje_{uuid.uuid4().hex[:12]}"

    viaje_doc = {
        "viaje_id": viaje_id,
        "linea_id": linea["linea_id"],
        "linea_nombre": linea["nombre_linea"],
        # Ruta
        "origen": data.origen,
        "destino": data.destino,
        "fecha_salida": data.fecha_salida,
        # Pricing
        "precio_asiento": data.precio_asiento,
        # Vehículo asignado
        "vehiculo_id": vehiculo["vehiculo_id"],
        "vehiculo_info": {
            "placa": vehiculo["placa"],
            "marca": vehiculo["marca"],
            "modelo": vehiculo["modelo"],
            "tipo": vehiculo["tipo_vehiculo"],
        },
        # Chofer asignado
        "chofer_id": data.chofer_id,
        "chofer_info": chofer_info,
        # Capacidad
        "capacidad_total": capacidad,
        "puestos_disponibles": capacidad,
        "puestos_vendidos": 0,
        # Financiero
        "ingreso_potencial": ingreso_potencial,
        "comision_esperada": comision_maxima,
        # Detalles
        "descripcion": data.descripcion,
        "punto_encuentro": data.punto_encuentro,
        "status": "programado",
        "reservas": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.viajes_interurbano.insert_one(viaje_doc)

    if "_id" in viaje_doc:
        del viaje_doc["_id"]

    return {"message": "Viaje programado creado exitosamente", "viaje": viaje_doc}


@router.get("/viajes")
async def listar_mis_viajes(
    status: Optional[str] = None, user: dict = Depends(get_current_user)
):
    """Listar viajes de mi Línea"""
    linea = await verify_line_admin(user)

    query = {"linea_id": linea["linea_id"]}
    if status:
        query["status"] = status

    viajes = (
        await db.viajes_interurbano.find(query, {"_id": 0})
        .sort("fecha_salida", 1)
        .to_list(100)
    )

    return viajes


@router.patch("/viajes/{viaje_id}/asignar-chofer")
async def asignar_chofer(
    viaje_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """Asignar o cambiar el chofer de un viaje"""
    linea = await verify_line_admin(user)
    body = await request.json()
    chofer_id = body.get("chofer_id")

    if not chofer_id:
        raise HTTPException(status_code=400, detail="chofer_id es requerido")

    viaje = await db.viajes_interurbano.find_one(
        {"viaje_id": viaje_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")

    if viaje["status"] not in ["programado"]:
        raise HTTPException(
            status_code=400, detail="Solo puedes asignar chofer a viajes programados"
        )

    chofer = await db.choferes_linea.find_one(
        {"chofer_id": chofer_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not chofer:
        raise HTTPException(status_code=404, detail="Chofer no encontrado en tu línea")

    chofer_info = {
        "chofer_id": chofer["chofer_id"],
        "nombre": chofer["nombre"],
        "telefono": chofer["telefono"],
    }

    await db.viajes_interurbano.update_one(
        {"viaje_id": viaje_id},
        {"$set": {"chofer_id": chofer_id, "chofer_info": chofer_info}},
    )

    return {"message": f"Chofer {chofer['nombre']} asignado al viaje"}


@router.post("/viajes/{viaje_id}/iniciar")
async def iniciar_viaje(viaje_id: str, user: dict = Depends(get_current_user)):
    """Iniciar un viaje (cambiar status a en_curso)"""
    linea = await verify_line_admin(user)

    viaje = await db.viajes_interurbano.find_one(
        {"viaje_id": viaje_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")

    if viaje["status"] != "programado":
        raise HTTPException(status_code=400, detail="Este viaje no puede iniciarse")

    if not viaje.get("chofer_id"):
        raise HTTPException(
            status_code=400, detail="Debes asignar un chofer antes de iniciar el viaje"
        )

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

    La comisión del 10% se descuenta de la billetera de la LÍNEA.
    """
    linea = await verify_line_admin(user)

    viaje = await db.viajes_interurbano.find_one(
        {"viaje_id": viaje_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")

    if viaje["status"] == "completado":
        raise HTTPException(status_code=400, detail="Este viaje ya fue completado")

    # Obtener tasa de comisión desde la configuración del admin
    commission_rate = await get_commission_rate("linea")

    # Calcular comisión real basada en boletos vendidos
    ingresos_reales = viaje["puestos_vendidos"] * viaje["precio_asiento"]
    comision = ingresos_reales * commission_rate

    # Descontar comisión de la wallet de la LÍNEA
    await db.lineas_transporte.update_one(
        {"linea_id": linea["linea_id"]},
        {
            "$inc": {
                "wallet_balance": -comision,
                "total_viajes": 1,
                "total_pasajeros": viaje["puestos_vendidos"],
                "total_earnings": ingresos_reales - comision,
            }
        },
    )

    # Registrar transacción de comisión
    await db.transactions.insert_one(
        {
            "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
            "entity_type": "linea",
            "entity_id": linea["linea_id"],
            "amount_usd": -comision,
            "type": TransactionType.COMMISSION_DEDUCTION.value,
            "status": "completed",
            "reference": viaje_id,
            "description": f"Comisión {int(commission_rate*100)}% - Viaje {viaje['origen']}-{viaje['destino']} "
            f"({viaje['puestos_vendidos']} boletos / ${ingresos_reales:.2f})",
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

    # Actualizar estadísticas del chofer
    if viaje.get("chofer_id"):
        await db.choferes_linea.update_one(
            {"chofer_id": viaje["chofer_id"]}, {"$inc": {"total_viajes": 1}}
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
    linea = await verify_line_admin(user)

    viaje = await db.viajes_interurbano.find_one(
        {"viaje_id": viaje_id, "linea_id": linea["linea_id"]}, {"_id": 0}
    )

    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")

    if viaje["puestos_vendidos"] > 0:
        raise HTTPException(
            status_code=400,
            detail="No puedes cancelar un viaje con boletos vendidos. "
            "Contacta a los pasajeros primero.",
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


# ==================== ENDPOINTS PÚBLICOS PARA CLIENTES ====================


@router.get("/viajes/buscar")
async def buscar_viajes(
    origen: Optional[str] = None,
    destino: Optional[str] = None,
    fecha: Optional[str] = None,
):
    """
    Buscar viajes disponibles (público para clientes).
    Los viajes incluyen info de la Línea y del Chofer.
    """
    query = {"status": "programado", "puestos_disponibles": {"$gt": 0}}

    if origen:
        query["origen"] = {"$regex": origen, "$options": "i"}
    if destino:
        query["destino"] = {"$regex": destino, "$options": "i"}
    if fecha:
        query["fecha_salida"] = {"$regex": f"^{fecha}"}

    viajes = (
        await db.viajes_interurbano.find(
            query, {"_id": 0, "reservas": 0}  # Excluir lista de reservas por privacidad
        )
        .sort("fecha_salida", 1)
        .to_list(50)
    )

    return viajes


@router.get("/viajes/{viaje_id}")
async def get_viaje_detalle(viaje_id: str):
    """Obtener detalles de un viaje (público)"""
    viaje = await db.viajes_interurbano.find_one(
        {"viaje_id": viaje_id}, {"_id": 0, "reservas": 0}
    )
    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    return viaje


@router.post("/viajes/{viaje_id}/comprar")
async def comprar_boletos(
    viaje_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """
    Comprar boletos para un viaje.
    El boleto muestra: Línea, Chofer asignado, Vehículo.
    """
    body = await request.json()
    cantidad_puestos = body.get("cantidad_puestos", 1)
    nombre_pasajero = body.get("nombre_pasajero")
    telefono_pasajero = body.get("telefono_pasajero")
    cedula_pasajero = body.get("cedula_pasajero")

    viaje = await db.viajes_interurbano.find_one({"viaje_id": viaje_id}, {"_id": 0})

    if not viaje:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")

    if viaje["status"] != "programado":
        raise HTTPException(
            status_code=400, detail="Este viaje no está disponible para reservas"
        )

    if cantidad_puestos <= 0:
        raise HTTPException(status_code=400, detail="Cantidad de puestos inválida")

    if cantidad_puestos > viaje["puestos_disponibles"]:
        raise HTTPException(
            status_code=400,
            detail=f"Solo quedan {viaje['puestos_disponibles']} puestos disponibles",
        )

    total = cantidad_puestos * viaje["precio_asiento"]
    reserva_id = f"res_{uuid.uuid4().hex[:12]}"

    # Obtener info del chofer si está asignado
    chofer_nombre = None
    chofer_telefono = None
    if viaje.get("chofer_info"):
        chofer_nombre = viaje["chofer_info"].get("nombre")
        chofer_telefono = viaje["chofer_info"].get("telefono")

    vehiculo_placa = None
    if viaje.get("vehiculo_info"):
        vehiculo_placa = viaje["vehiculo_info"].get("placa")

    reserva = {
        "reserva_id": reserva_id,
        "user_id": user["user_id"],
        "nombre_pasajero": nombre_pasajero or user.get("name"),
        "telefono_pasajero": telefono_pasajero or user.get("phone"),
        "cedula_pasajero": cedula_pasajero,
        "cantidad_puestos": cantidad_puestos,
        "precio_unitario": viaje["precio_asiento"],
        "total": total,
        "status": "confirmada",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Actualizar viaje con la reserva
    await db.viajes_interurbano.update_one(
        {"viaje_id": viaje_id},
        {
            "$push": {"reservas": reserva},
            "$inc": {
                "puestos_disponibles": -cantidad_puestos,
                "puestos_vendidos": cantidad_puestos,
            },
        },
    )

    # Guardar reserva completa para el cliente
    reserva_completa = {
        **reserva,
        "viaje_id": viaje_id,
        "linea_nombre": viaje["linea_nombre"],
        "chofer_nombre": chofer_nombre,
        "chofer_telefono": chofer_telefono,
        "vehiculo_placa": vehiculo_placa,
        "origen": viaje["origen"],
        "destino": viaje["destino"],
        "fecha_salida": viaje["fecha_salida"],
        "punto_encuentro": viaje.get("punto_encuentro"),
    }
    await db.reservas_interurbano.insert_one(reserva_completa)

    return {
        "message": f"¡Reserva confirmada! {cantidad_puestos} puesto(s) reservado(s)",
        "reserva_id": reserva_id,
        "boleto": {
            "linea": viaje["linea_nombre"],
            "chofer": chofer_nombre or "Por asignar",
            "vehiculo_placa": vehiculo_placa,
            "origen": viaje["origen"],
            "destino": viaje["destino"],
            "fecha_salida": viaje["fecha_salida"],
            "punto_encuentro": viaje.get("punto_encuentro"),
        },
        "detalles": {
            "cantidad_puestos": cantidad_puestos,
            "precio_unitario": viaje["precio_asiento"],
            "total_a_pagar": total,
        },
        "nota": "Paga el total al chofer al momento de abordar (Efectivo o Pago Móvil)",
    }


@router.get("/mis-reservas")
async def get_mis_reservas(user: dict = Depends(get_current_user)):
    """Obtener reservas del cliente"""
    reservas = (
        await db.reservas_interurbano.find({"user_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )

    return reservas


@router.delete("/reservas/{reserva_id}")
async def cancelar_reserva(reserva_id: str, user: dict = Depends(get_current_user)):
    """Cancelar una reserva"""
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


@router.get("/rutas-populares")
async def get_rutas_populares():
    """Obtener rutas populares con viajes próximos"""
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

from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
import uuid

from utils.database import db
from utils.auth import get_current_user
from models.wallet_models import (
    TransactionType,
    ACTIVATION_FEE_AMOUNT,
    MIN_BALANCE_TO_ACTIVATE,
)
from models.user_models import KYC_ELEVATABLE_ROLES

router = APIRouter(prefix="/admin", tags=["Admin"])


# ==================== KPIs GLOBALES ====================


@router.get("/stats")
async def get_admin_stats(user: dict = Depends(get_current_user)):
    """Obtener estadísticas globales para el panel admin"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    # Usuarios totales por rol
    users_count = await db.users.count_documents({})

    # Busetas activas (recorridos activos)
    busetas_activas = await db.recorridos_urbanos.count_documents({})

    # Conductores pendientes/aprobados (legacy)
    drivers_pending = await db.drivers.count_documents({"status": "pending"})
    drivers_approved = await db.drivers.count_documents({"status": "approved"})

    # Servicios/viajes programados
    services_active = await db.services.count_documents(
        {"status": {"$in": ["pending", "accepted", "in_progress"]}}
    )
    viajes_programados = await db.viajes.count_documents(
        {"status": {"$in": ["scheduled", "boarding"]}}
    )

    # Órdenes del market
    orders_count = await db.orders.count_documents({})

    # Líneas urbanas activas
    lineas_urbanas = await db.lineas_urbanas.count_documents({"status": "approved"})

    # Rutas urbanas
    rutas_urbanas = await db.rutas_urbanas_v2.count_documents({"status": "active"})

    # Volumen transaccionado (aggregation pipeline)
    vol_result = await db.transactions.aggregate(
        [{"$group": {"_id": None, "total": {"$sum": {"$abs": "$amount_usd"}}}}]
    ).to_list(1)
    volumen_total = vol_result[0]["total"] if vol_result else 0

    # Ingresos de plataforma (fees + comisiones)
    fee_result = await db.transactions.aggregate(
        [
            {
                "$match": {
                    "type": {
                        "$in": [
                            TransactionType.ACTIVATION_FEE.value,
                            TransactionType.COMMISSION_DEDUCTION.value,
                            "TOLL",
                        ]
                    }
                }
            },
            {"$group": {"_id": None, "total": {"$sum": {"$abs": "$amount_usd"}}}},
        ]
    ).to_list(1)
    ingresos_omni = fee_result[0]["total"] if fee_result else 0

    # Micropagos urbanos
    micro_result = await db.micropagos_urbanos.aggregate(
        [{"$group": {"_id": None, "total": {"$sum": "$fee_omni"}}}]
    ).to_list(1)
    ingresos_urbanos = micro_result[0]["total"] if micro_result else 0

    return {
        "users": users_count,
        "drivers": drivers_approved,
        "pending_drivers": drivers_pending,
        "services": services_active,
        "orders": orders_count,
        "busetas_activas": busetas_activas,
        "lineas_urbanas": lineas_urbanas,
        "rutas_urbanas": rutas_urbanas,
        "viajes_programados": viajes_programados,
        "volumen_transaccionado": round(volumen_total, 2),
        "ingresos_plataforma": round(ingresos_omni + ingresos_urbanos, 2),
    }


@router.get("/drivers")
async def get_drivers_list(user: dict = Depends(get_current_user)):
    """Obtener lista de conductores (legacy)"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    drivers = await db.drivers.find({}, {"_id": 0}).to_list(100)
    return drivers


@router.get("/transactions")
async def get_transactions_list(user: dict = Depends(get_current_user)):
    """Obtener lista de transacciones recientes"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    transactions = (
        await db.transactions.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    )
    return transactions


# ==================== KYC / VERIFICACIÓN DE SOCIOS ====================


@router.get("/kyc-requests")
async def get_kyc_requests(status: str = None, user: dict = Depends(get_current_user)):
    """
    Obtener solicitudes KYC desde la colección unificada.
    Filtrar por status: pending, approved, rejected, all
    """
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    query = {}
    if status and status != "all":
        query["status"] = status

    requests = await db.kyc_requests.find(query, {"_id": 0}).to_list(100)

    # Ordenar por fecha (más recientes primero)
    requests.sort(
        key=lambda x: x.get("submitted_at") or x.get("created_at", ""), reverse=True
    )

    return {
        "requests": requests,
        "total": len(requests),
        "pending_count": len([r for r in requests if r.get("status") == "pending"]),
        "approved_count": len([r for r in requests if r.get("status") == "approved"]),
        "rejected_count": len([r for r in requests if r.get("status") == "rejected"]),
    }


@router.get("/kyc-requests/{kyc_id}")
async def get_kyc_request_detail(kyc_id: str, user: dict = Depends(get_current_user)):
    """Obtener detalle de una solicitud KYC específica"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    kyc = await db.kyc_requests.find_one({"kyc_id": kyc_id}, {"_id": 0})
    if not kyc:
        raise HTTPException(status_code=404, detail="Solicitud KYC no encontrada")

    return kyc


@router.post("/kyc-requests/{kyc_id}/approve")
async def approve_kyc_request(kyc_id: str, user: dict = Depends(get_current_user)):
    """Aprobar solicitud KYC y actualizar rol del usuario"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    kyc = await db.kyc_requests.find_one({"kyc_id": kyc_id})
    if not kyc:
        raise HTTPException(status_code=404, detail="Solicitud KYC no encontrada")

    if kyc.get("status") == "approved":
        return {"message": "Ya está aprobado", "kyc_id": kyc_id}

    now = datetime.now(timezone.utc).isoformat()

    # Actualizar KYC
    await db.kyc_requests.update_one(
        {"kyc_id": kyc_id},
        {
            "$set": {
                "status": "approved",
                "reviewed_at": now,
                "reviewed_by": user.get("email"),
                "approved_at": now,
            }
        },
    )

    # Actualizar usuario con nuevo rol
    user_id = kyc.get("user_id")
    requested_role = kyc.get("requested_role")
    sub_role = kyc.get("sub_role")

    # Defensa en profundidad: nunca elevar a un rol fuera de la whitelist KYC.
    update_data = {"kyc_status": "approved"}
    if requested_role in KYC_ELEVATABLE_ROLES:
        update_data["role"] = requested_role
    if sub_role:
        update_data["sub_role"] = sub_role

    await db.users.update_one(
        {"user_id": user_id}, {"$set": update_data, "$unset": {"pending_role": ""}}
    )

    # Enviar notificación al usuario
    role_labels = {
        "socio_conductor": "Conductor",
        "socio_repartidor": "Repartidor",
        "carga_pesada": "Operador de Carga Pesada",
        "chofer_linea": "Chofer Interurbano",
        "chofer_urbano": "Chofer Urbano",
        "line_admin": "Administrador de Terminal",
        "urban_line_admin": "Administrador de Línea Urbana",
        "socio_comercial": "Socio Comercial",
        "rent_owner": "Propietario Rent-a-Car",
    }
    role_label = role_labels.get(requested_role, requested_role)

    notification = {
        "notification_id": f"notif_{now.replace(':', '').replace('-', '').replace('.', '')[:20]}",
        "user_id": user_id,
        "type": "kyc_approved",
        "message": f"¡Felicitaciones! Tu solicitud KYC ha sido aprobada. Ya eres {role_label}.",
        "data": {"status": "approved", "role": requested_role},
        "read": False,
        "created_at": now,
    }
    await db.notifications.insert_one(notification)

    return {
        "message": f"KYC aprobado. Usuario actualizado a rol: {requested_role}",
        "kyc_id": kyc_id,
        "user_id": user_id,
        "new_role": requested_role,
    }


@router.post("/kyc-requests/{kyc_id}/reject")
async def reject_kyc_request(
    kyc_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """Rechazar solicitud KYC con razón"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    body = await request.json()
    reason = body.get("reason", "Documentos no cumplen requisitos")

    kyc = await db.kyc_requests.find_one({"kyc_id": kyc_id})
    if not kyc:
        raise HTTPException(status_code=404, detail="Solicitud KYC no encontrada")

    now = datetime.now(timezone.utc).isoformat()

    await db.kyc_requests.update_one(
        {"kyc_id": kyc_id},
        {
            "$set": {
                "status": "rejected",
                "rejection_reason": reason,
                "reviewed_at": now,
                "reviewed_by": user.get("email"),
            }
        },
    )

    # Actualizar usuario
    await db.users.update_one(
        {"user_id": kyc.get("user_id")}, {"$set": {"kyc_status": "rejected"}}
    )

    # Enviar notificación de rechazo
    notification = {
        "notification_id": f"notif_{now.replace(':', '').replace('-', '').replace('.', '')[:20]}",
        "user_id": kyc.get("user_id"),
        "type": "kyc_rejected",
        "message": f"Tu solicitud KYC ha sido rechazada. Razón: {reason}",
        "data": {"status": "rejected", "reason": reason},
        "read": False,
        "created_at": now,
    }
    await db.notifications.insert_one(notification)

    return {"message": "KYC rechazado", "kyc_id": kyc_id, "reason": reason}


# LEGACY: Mantener endpoint viejo para compatibilidad
@router.get("/kyc/all-pending")
async def get_all_pending_kyc(user: dict = Depends(get_current_user)):
    """
    Obtener TODAS las solicitudes KYC pendientes unificadas.
    Incluye: conductores, repartidores, comerciales, líneas urbanas, rent owners.
    """
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    pending = []

    # Socios Conductores
    conductores = await db.socios_conductores.find(
        {"status": "pending_kyc"}, {"_id": 0}
    ).to_list(100)
    for c in conductores:
        user_info = await db.users.find_one(
            {"user_id": c.get("user_id")}, {"_id": 0, "name": 1, "email": 1, "phone": 1}
        )
        pending.append(
            {
                "type": "socio_conductor",
                "id": c.get("socio_id"),
                "user_id": c.get("user_id"),
                "name": user_info.get("name", "N/A") if user_info else "N/A",
                "email": user_info.get("email", "N/A") if user_info else "N/A",
                "phone": user_info.get("phone", "") if user_info else "",
                "vehicle_type": c.get("vehicle_type"),
                "plate_number": c.get("plate_number"),
                "documents": {
                    "cedula_url": c.get("cedula_url"),
                    "license_url": c.get("license_url"),
                    "vehicle_photo_url": c.get("vehicle_photo_url"),
                    "circulation_card_url": c.get("circulation_card_url"),
                    "rcv_insurance_url": c.get("rcv_insurance_url"),
                },
                "created_at": c.get("created_at"),
            }
        )

    # Socios Repartidores
    repartidores = await db.socios_repartidores.find(
        {"status": "pending_kyc"}, {"_id": 0}
    ).to_list(100)
    for r in repartidores:
        user_info = await db.users.find_one(
            {"user_id": r.get("user_id")}, {"_id": 0, "name": 1, "email": 1, "phone": 1}
        )
        pending.append(
            {
                "type": "socio_repartidor",
                "id": r.get("socio_id"),
                "user_id": r.get("user_id"),
                "name": user_info.get("name", "N/A") if user_info else "N/A",
                "email": user_info.get("email", "N/A") if user_info else "N/A",
                "phone": user_info.get("phone", "") if user_info else "",
                "vehicle_type": r.get("vehicle_type"),
                "documents": {
                    "cedula_url": r.get("cedula_url"),
                    "frontal_photo_url": r.get("frontal_photo_url"),
                    "license_url": r.get("license_url"),
                },
                "created_at": r.get("created_at"),
            }
        )

    # Socios Comerciales
    comerciales = await db.socios_comerciales.find(
        {"status": "pending_kyc"}, {"_id": 0}
    ).to_list(100)
    for c in comerciales:
        user_info = await db.users.find_one(
            {"user_id": c.get("user_id")}, {"_id": 0, "name": 1, "email": 1, "phone": 1}
        )
        pending.append(
            {
                "type": "socio_comercial",
                "id": c.get("comercial_id"),
                "user_id": c.get("user_id"),
                "name": c.get("business_name")
                or (user_info.get("name", "N/A") if user_info else "N/A"),
                "email": user_info.get("email", "N/A") if user_info else "N/A",
                "phone": user_info.get("phone", "") if user_info else "",
                "business_type": c.get("business_type"),
                "documents": {
                    "rif_url": c.get("rif_url"),
                    "permit_url": c.get("permit_url"),
                    "store_photo_url": c.get("store_photo_url"),
                },
                "created_at": c.get("created_at"),
            }
        )

    # Líneas Urbanas
    lineas = await db.lineas_urbanas.find(
        {"status": "pending_kyc"}, {"_id": 0}
    ).to_list(100)
    for linea in lineas:
        user_info = await db.users.find_one(
            {"user_id": linea.get("admin_user_id")},
            {"_id": 0, "name": 1, "email": 1, "phone": 1},
        )
        pending.append(
            {
                "type": "linea_urbana",
                "id": linea.get("linea_id"),
                "user_id": linea.get("admin_user_id"),
                "name": linea.get("nombre_linea"),
                "email": linea.get("email_contacto")
                or (user_info.get("email", "N/A") if user_info else "N/A"),
                "phone": linea.get("telefono_contacto")
                or (user_info.get("phone", "") if user_info else ""),
                "rif": linea.get("rif"),
                "zona_operacion": linea.get("zona_operacion"),
                "documents": {"logo_url": linea.get("logo_url")},
                "created_at": linea.get("created_at"),
            }
        )

    # Rent Owners
    rent_owners = await db.rent_owners.find(
        {"status": "pending_kyc"}, {"_id": 0}
    ).to_list(100)
    for r in rent_owners:
        user_info = await db.users.find_one(
            {"user_id": r.get("user_id")}, {"_id": 0, "name": 1, "email": 1, "phone": 1}
        )
        pending.append(
            {
                "type": "rent_owner",
                "id": r.get("owner_id"),
                "user_id": r.get("user_id"),
                "name": r.get("business_name")
                or (user_info.get("name", "N/A") if user_info else "N/A"),
                "email": user_info.get("email", "N/A") if user_info else "N/A",
                "phone": user_info.get("phone", "") if user_info else "",
                "documents": {},
                "created_at": r.get("created_at"),
            }
        )

    # Ordenar por fecha de creación (más recientes primero)
    pending.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {"pending": pending, "total": len(pending)}


@router.post("/kyc/{type}/{entity_id}/approve")
async def approve_entity_kyc(
    type: str, entity_id: str, user: dict = Depends(get_current_user)
):
    """Aprobar KYC de cualquier tipo de entidad"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    now = datetime.now(timezone.utc).isoformat()

    if type == "socio_conductor":
        socio = await db.socios_conductores.find_one(
            {"socio_id": entity_id}, {"_id": 0}
        )
        if not socio:
            raise HTTPException(status_code=404, detail="No encontrado")
        fee_result = await process_activation_fee(socio["user_id"], "socio_conductor")
        await db.socios_conductores.update_one(
            {"socio_id": entity_id},
            {
                "$set": {
                    "status": "approved",
                    "activation_fee_paid": fee_result.get("activation_fee_paid", False),
                    "approved_at": now,
                }
            },
        )
        await db.users.update_one(
            {"user_id": socio["user_id"]}, {"$set": {"kyc_status": "approved"}}
        )
        return {"message": "Socio Conductor aprobado", "fee_info": fee_result}

    elif type == "socio_repartidor":
        socio = await db.socios_repartidores.find_one(
            {"socio_id": entity_id}, {"_id": 0}
        )
        if not socio:
            raise HTTPException(status_code=404, detail="No encontrado")
        fee_result = await process_activation_fee(socio["user_id"], "socio_repartidor")
        await db.socios_repartidores.update_one(
            {"socio_id": entity_id},
            {
                "$set": {
                    "status": "approved",
                    "activation_fee_paid": fee_result.get("activation_fee_paid", False),
                    "approved_at": now,
                }
            },
        )
        await db.users.update_one(
            {"user_id": socio["user_id"]}, {"$set": {"kyc_status": "approved"}}
        )
        return {"message": "Socio Repartidor aprobado", "fee_info": fee_result}

    elif type == "socio_comercial":
        socio = await db.socios_comerciales.find_one(
            {"comercial_id": entity_id}, {"_id": 0}
        )
        if not socio:
            raise HTTPException(status_code=404, detail="No encontrado")
        fee_result = await process_activation_fee(socio["user_id"], "socio_comercial")
        await db.socios_comerciales.update_one(
            {"comercial_id": entity_id},
            {
                "$set": {
                    "status": "approved",
                    "activation_fee_paid": fee_result.get("activation_fee_paid", False),
                    "approved_at": now,
                }
            },
        )
        await db.users.update_one(
            {"user_id": socio["user_id"]}, {"$set": {"kyc_status": "approved"}}
        )
        return {"message": "Socio Comercial aprobado", "fee_info": fee_result}

    elif type == "linea_urbana":
        linea = await db.lineas_urbanas.find_one({"linea_id": entity_id}, {"_id": 0})
        if not linea:
            raise HTTPException(status_code=404, detail="No encontrado")
        await db.lineas_urbanas.update_one(
            {"linea_id": entity_id},
            {"$set": {"status": "approved", "approved_at": now}},
        )
        await db.users.update_one(
            {"user_id": linea["admin_user_id"]}, {"$set": {"kyc_status": "approved"}}
        )
        return {"message": "Línea Urbana aprobada"}

    elif type == "rent_owner":
        owner = await db.rent_owners.find_one({"owner_id": entity_id}, {"_id": 0})
        if not owner:
            raise HTTPException(status_code=404, detail="No encontrado")
        await db.rent_owners.update_one(
            {"owner_id": entity_id},
            {"$set": {"status": "approved", "approved_at": now}},
        )
        await db.users.update_one(
            {"user_id": owner["user_id"]}, {"$set": {"kyc_status": "approved"}}
        )
        return {"message": "Rent Owner aprobado"}

    else:
        raise HTTPException(status_code=400, detail="Tipo no válido")


@router.post("/kyc/{type}/{entity_id}/reject")
async def reject_entity_kyc(
    type: str, entity_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """Rechazar KYC de cualquier tipo de entidad"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    body = await request.json()
    reason = body.get("reason", "Documentación insuficiente")
    now = datetime.now(timezone.utc).isoformat()

    collections_map = {
        "socio_conductor": ("socios_conductores", "socio_id"),
        "socio_repartidor": ("socios_repartidores", "socio_id"),
        "socio_comercial": ("socios_comerciales", "comercial_id"),
        "linea_urbana": ("lineas_urbanas", "linea_id"),
        "rent_owner": ("rent_owners", "owner_id"),
    }

    if type not in collections_map:
        raise HTTPException(status_code=400, detail="Tipo no válido")

    collection_name, id_field = collections_map[type]
    collection = getattr(db, collection_name)

    result = await collection.update_one(
        {id_field: entity_id},
        {
            "$set": {
                "status": "rejected",
                "rejection_reason": reason,
                "rejected_at": now,
            }
        },
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="No encontrado")

    return {"message": f"{type} rechazado", "reason": reason}


# ==================== CONTROL DE VERTICALES ====================


@router.get("/verticales/urbanas")
async def get_lineas_urbanas(user: dict = Depends(get_current_user)):
    """Obtener información de todas las líneas de transporte urbano"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    lineas = await db.lineas_urbanas.find({}, {"_id": 0}).to_list(100)

    for linea in lineas:
        # Contar recursos
        vehiculos = await db.vehiculos_urbanos.count_documents(
            {"linea_id": linea["linea_id"]}
        )
        choferes = await db.choferes_urbanos.count_documents(
            {"linea_id": linea["linea_id"]}
        )
        rutas = await db.rutas_urbanas_v2.count_documents(
            {"linea_id": linea["linea_id"]}
        )

        linea["vehiculos_count"] = vehiculos
        linea["choferes_count"] = choferes
        linea["rutas_count"] = rutas

    return lineas


@router.get("/verticales/rent-a-car")
async def get_rent_stats(user: dict = Depends(get_current_user)):
    """Obtener estadísticas del módulo Rent-a-Car"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    owners_count = await db.rent_owners.count_documents({})
    vehicles_count = await db.rent_vehicles.count_documents({})
    active_rentals = await db.rentals.count_documents(
        {"status": {"$in": ["active", "pending"]}}
    )

    # Top 5 owners by vehicles
    owners = await db.rent_owners.find({}, {"_id": 0}).to_list(10)

    return {
        "owners_count": owners_count,
        "vehicles_count": vehicles_count,
        "active_rentals": active_rentals,
        "owners": owners,
    }


@router.get("/verticales/carga")
async def get_carga_stats(user: dict = Depends(get_current_user)):
    """Obtener estadísticas del módulo de Carga Pesada"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    operadores = await db.operadores_carga.count_documents({})
    vehiculos = await db.vehiculos_carga.count_documents({})
    servicios_activos = await db.servicios_carga.count_documents(
        {"status": {"$in": ["pending", "assigned", "in_progress"]}}
    )

    return {
        "operadores_count": operadores,
        "vehiculos_count": vehiculos,
        "servicios_activos": servicios_activos,
    }


@router.get("/verticales/terminales")
async def get_terminales_stats(user: dict = Depends(get_current_user)):
    """Obtener estadísticas de los terminales interurbanos (B2B)"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    lineas = await db.lineas_transporte.count_documents({})
    vehiculos = await db.vehiculos_linea.count_documents({})
    choferes = await db.choferes_linea.count_documents({})
    rutas = await db.rutas.count_documents({})
    viajes_hoy = await db.viajes.count_documents(
        {"status": {"$in": ["scheduled", "boarding", "in_transit"]}}
    )

    return {
        "lineas_count": lineas,
        "vehiculos_count": vehiculos,
        "choferes_count": choferes,
        "rutas_count": rutas,
        "viajes_activos": viajes_hoy,
    }


# ==================== CONFIGURACIÓN FINANCIERA ====================


@router.get("/config/financial")
async def get_financial_config(user: dict = Depends(get_current_user)):
    """Obtener configuración financiera actual"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    # Buscar configuración existente o usar defaults
    config = await db.platform_config.find_one({"type": "financial"}, {"_id": 0})

    if not config:
        config = {
            "type": "financial",
            "exchange_rate": 50.0,
            "toll_moto": 0.50,
            "toll_others": 1.00,
            "commission_transport": 0.10,  # 10% comisión conductores
            "commission_market": 0.12,  # 12% comisión market
            "commission_rent": 0.10,  # 10% comisión rent-a-car
            "commission_interurbano": 0.10,  # 10% comisión terminales interurbanos
            "commission_linea": 0.10,  # 10% comisión líneas de transporte
            "urban_fee_fixed": 0.02,  # Fee fijo transporte urbano
            "activation_fee": ACTIVATION_FEE_AMOUNT,
            "min_balance_activate": MIN_BALANCE_TO_ACTIVATE,
            "delivery_fee_base": 2.00,  # Fee base delivery
            "line_activation_fee": 5.00,  # Fee activación líneas
        }
        await db.platform_config.insert_one(config)

    return config


@router.post("/config/financial")
async def update_financial_config(
    request: Request, user: dict = Depends(get_current_user)
):
    """Actualizar configuración financiera"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    body = await request.json()

    allowed_fields = [
        "exchange_rate",
        "toll_moto",
        "toll_others",
        "commission_transport",
        "commission_market",
        "commission_rent",
        "commission_interurbano",
        "commission_linea",
        "urban_fee_fixed",
        "activation_fee",
        "min_balance_activate",
        "delivery_fee_base",
        "line_activation_fee",
    ]

    update_data = {k: v for k, v in body.items() if k in allowed_fields}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = user["user_id"]

    await db.platform_config.update_one(
        {"type": "financial"}, {"$set": update_data}, upsert=True
    )

    return {"message": "Configuración actualizada", "updated": update_data}


async def process_activation_fee(user_id: str, socio_type: str) -> dict:
    """
    Procesa el fee de activación automáticamente cuando un socio es aprobado.

    Regla: Si el usuario tiene >= $5.00 en balance, se descuenta $1.00 automáticamente.

    Returns:
        dict con información del procesamiento del fee
    """
    wallet_user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not wallet_user:
        return {"fee_processed": False, "reason": "Usuario no encontrado"}

    balance = wallet_user.get("wallet_balance", 0)
    held = wallet_user.get("wallet_held", 0)
    available = balance - held

    # Verificar si tiene saldo suficiente para el fee
    if available < MIN_BALANCE_TO_ACTIVATE:
        return {
            "fee_processed": False,
            "reason": f"Saldo insuficiente. Requiere ${MIN_BALANCE_TO_ACTIVATE:.2f}, tiene ${available:.2f}",
            "activation_fee_paid": False,
        }

    # Descontar el fee de activación
    await db.users.update_one(
        {"user_id": user_id}, {"$inc": {"wallet_balance": -ACTIVATION_FEE_AMOUNT}}
    )

    # Registrar la transacción
    transaction = {
        "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "amount_usd": -ACTIVATION_FEE_AMOUNT,
        "type": TransactionType.ACTIVATION_FEE.value,
        "status": "completed",
        "reference": f"activation_{socio_type}",
        "description": f"Fee de activación - {socio_type}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.transactions.insert_one(transaction)

    return {
        "fee_processed": True,
        "fee_amount": ACTIVATION_FEE_AMOUNT,
        "new_balance": available - ACTIVATION_FEE_AMOUNT,
        "activation_fee_paid": True,
        "transaction_id": transaction["transaction_id"],
    }


@router.post("/kyc/conductor/{socio_id}/approve")
async def approve_conductor_kyc(socio_id: str, user: dict = Depends(get_current_user)):
    """
    Aprobar KYC de Socio Conductor.

    Al aprobar, si el usuario tiene >= $5.00 en su billetera:
    - Se descuenta automáticamente $1.00 como fee de activación
    - Se marca activation_fee_paid = True
    """
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    socio = await db.socios_conductores.find_one({"socio_id": socio_id}, {"_id": 0})
    if not socio:
        raise HTTPException(status_code=404, detail="Socio no encontrado")

    # Procesar fee de activación
    fee_result = await process_activation_fee(socio["user_id"], "socio_conductor")

    # Actualizar estado del socio
    await db.socios_conductores.update_one(
        {"socio_id": socio_id},
        {
            "$set": {
                "status": "approved",
                "activation_fee_paid": fee_result.get("activation_fee_paid", False),
                "approved_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Actualizar usuario
    await db.users.update_one(
        {"user_id": socio["user_id"]}, {"$set": {"kyc_status": "approved"}}
    )

    return {"message": "Socio Conductor aprobado", "fee_info": fee_result}


@router.post("/kyc/repartidor/{socio_id}/approve")
async def approve_repartidor_kyc(socio_id: str, user: dict = Depends(get_current_user)):
    """
    Aprobar KYC de Socio Repartidor.

    Al aprobar, si el usuario tiene >= $5.00 en su billetera:
    - Se descuenta automáticamente $1.00 como fee de activación
    - Se marca activation_fee_paid = True
    """
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    socio = await db.socios_repartidores.find_one({"socio_id": socio_id}, {"_id": 0})
    if not socio:
        raise HTTPException(status_code=404, detail="Socio no encontrado")

    # Procesar fee de activación
    fee_result = await process_activation_fee(socio["user_id"], "socio_repartidor")

    # Actualizar estado del socio
    await db.socios_repartidores.update_one(
        {"socio_id": socio_id},
        {
            "$set": {
                "status": "approved",
                "activation_fee_paid": fee_result.get("activation_fee_paid", False),
                "approved_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Actualizar usuario
    await db.users.update_one(
        {"user_id": socio["user_id"]}, {"$set": {"kyc_status": "approved"}}
    )

    return {"message": "Socio Repartidor aprobado", "fee_info": fee_result}


@router.post("/kyc/comercial/{socio_id}/approve")
async def approve_comercial_kyc(socio_id: str, user: dict = Depends(get_current_user)):
    """
    Aprobar KYC de Socio Comercial.

    Al aprobar, si el usuario tiene >= $5.00 en su billetera:
    - Se descuenta automáticamente $1.00 como fee de activación
    - Se marca activation_fee_paid = True
    """
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    socio = await db.socios_comerciales.find_one({"comercial_id": socio_id}, {"_id": 0})
    if not socio:
        raise HTTPException(status_code=404, detail="Socio Comercial no encontrado")

    # Procesar fee de activación
    fee_result = await process_activation_fee(socio["user_id"], "socio_comercial")

    # Actualizar estado del socio
    await db.socios_comerciales.update_one(
        {"comercial_id": socio_id},
        {
            "$set": {
                "status": "approved",
                "activation_fee_paid": fee_result.get("activation_fee_paid", False),
                "approved_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Actualizar usuario
    await db.users.update_one(
        {"user_id": socio["user_id"]}, {"$set": {"kyc_status": "approved"}}
    )

    return {"message": "Socio Comercial aprobado", "fee_info": fee_result}


@router.get("/kyc/pending")
async def get_pending_kyc(user: dict = Depends(get_current_user)):
    """Obtener todos los KYC pendientes"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    conductores = await db.socios_conductores.find(
        {"status": "pending_kyc"}, {"_id": 0}
    ).to_list(100)
    repartidores = await db.socios_repartidores.find(
        {"status": "pending_kyc"}, {"_id": 0}
    ).to_list(100)
    comerciales = await db.socios_comerciales.find(
        {"status": "pending_kyc"}, {"_id": 0}
    ).to_list(100)

    return {
        "conductores": conductores,
        "repartidores": repartidores,
        "comerciales": comerciales,
    }


@router.get("/financial/stats")
async def get_financial_stats(user: dict = Depends(get_current_user)):
    """Obtener estadísticas financieras de la plataforma"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")

    # Total de fees de activación cobrados
    activation_fees = await db.transactions.find(
        {"type": TransactionType.ACTIVATION_FEE.value}, {"_id": 0}
    ).to_list(1000)
    total_activation_fees = sum(abs(t.get("amount_usd", 0)) for t in activation_fees)

    # Total de comisiones cobradas
    commissions = await db.transactions.find(
        {"type": TransactionType.COMMISSION_DEDUCTION.value}, {"_id": 0}
    ).to_list(1000)
    total_commissions = sum(abs(t.get("amount_usd", 0)) for t in commissions)

    # Socios activos
    conductores_activos = await db.socios_conductores.count_documents(
        {"status": "approved"}
    )
    repartidores_activos = await db.socios_repartidores.count_documents(
        {"status": "approved"}
    )
    comerciales_activos = await db.socios_comerciales.count_documents(
        {"status": "approved"}
    )

    return {
        "total_activation_fees_usd": total_activation_fees,
        "total_commissions_usd": total_commissions,
        "total_platform_revenue_usd": total_activation_fees + total_commissions,
        "active_partners": {
            "conductores": conductores_activos,
            "repartidores": repartidores_activos,
            "comerciales": comerciales_activos,
            "total": conductores_activos + repartidores_activos + comerciales_activos,
        },
    }

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import uuid

from utils.database import db
from utils.auth import get_current_user
from utils.financial_config import get_commission_rate, get_financial_config
from models.market_models import OrderCreate
from models.wallet_models import TransactionType

router = APIRouter(prefix="/market", tags=["Market"])


@router.get("/stores")
async def get_market_stores(category: str = None):
    query = {"is_active": True}
    if category:
        query["category"] = category
    stores = await db.market_stores.find(query, {"_id": 0}).to_list(100)
    return stores


@router.get("/stores/{store_id}")
async def get_store(store_id: str):
    store = await db.market_stores.find_one({"store_id": store_id}, {"_id": 0})
    if not store:
        raise HTTPException(status_code=404, detail="Tienda no encontrada")
    return store


@router.get("/stores/{store_id}/products")
async def get_store_products(store_id: str):
    products = await db.market_products.find(
        {"store_id": store_id, "available": True}, {"_id": 0}
    ).to_list(100)
    return products


@router.get("/products")
async def get_all_products(store_id: str = None, category: str = None):
    """Get all products, optionally filtered by store_id or category"""
    query = {"available": True}
    if store_id:
        query["store_id"] = store_id
    if category:
        query["category"] = category

    products = await db.market_products.find(query, {"_id": 0}).to_list(200)
    return products


@router.post("/orders")
async def create_order(order: OrderCreate, user: dict = Depends(get_current_user)):
    """
    Crear un pedido del Market.

    MODELO DESCENTRALIZADO (configurable desde admin):
    - El cliente paga el total de productos directamente al comercio (Cash/Pago Móvil)
    - El cliente paga el costo de envío directamente al repartidor
    - Xuve descuenta el % configurado del total de productos del balance del Socio Comercial
    """
    # Obtener configuración financiera
    config = await get_financial_config()
    market_commission_rate = config["commission_market"]
    delivery_fee_base = config.get("delivery_fee_base", 2.00)

    products = []
    products_total = 0.0

    # Batch query: fetch all products in one query
    product_ids = [item.product_id for item in order.items]
    all_products = await db.market_products.find(
        {"product_id": {"$in": product_ids}}, {"_id": 0}
    ).to_list(len(product_ids))
    products_map = {p["product_id"]: p for p in all_products}

    for item in order.items:
        product = products_map.get(item.product_id)
        if product:
            products.append(
                {
                    "product_id": item.product_id,
                    "name": product["name"],
                    "price": product.get("price_usd") or product.get("price", 0),
                    "quantity": item.quantity,
                }
            )
            products_total += (
                product.get("price_usd") or product.get("price", 0)
            ) * item.quantity

    # Calcular comisión sobre productos (se cobrará al comercio)
    market_commission = products_total * market_commission_rate

    order_doc = {
        "order_id": f"order_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "store_id": order.store_id,
        "driver_id": None,
        "items": products,
        "products_total": products_total,  # Total de productos (pago al comercio)
        "delivery_fee": delivery_fee_base,  # Costo de envío (pago al repartidor)
        "total_usd": products_total + delivery_fee_base,  # Total general
        "commission": market_commission,  # Comisión (se cobra al comercio)
        "commission_rate": market_commission_rate,
        "status": "pending",
        "delivery_lat": order.delivery_lat,
        "delivery_lng": order.delivery_lng,
        "delivery_address": order.delivery_address,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.orders.insert_one(order_doc)

    if "_id" in order_doc:
        del order_doc["_id"]
    return order_doc


@router.post("/orders/{order_id}/confirm")
async def confirm_order(order_id: str, user: dict = Depends(get_current_user)):
    """
    Confirmar pedido y asignar repartidor.

    Busca repartidores disponibles que tengan:
    1. is_delivery_active = True
    2. status = approved
    3. is_online = True
    """
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Buscar repartidores disponibles con modo delivery activo
    available_repartidores = await db.socios_repartidores.find(
        {
            "status": "approved",
            "is_online": True,
            "is_available": True,
            "is_delivery_active": True,  # NUEVO: Solo repartidores con delivery activo
        },
        {"_id": 0},
    ).to_list(50)

    if not available_repartidores:
        return {
            "message": "Pedido confirmado. Buscando repartidores...",
            "order": order,
            "driver_assigned": False,
        }

    # Asignar al primero disponible (en producción usaríamos geolocalización)
    repartidor = available_repartidores[0]

    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "driver_id": repartidor["socio_id"],
                "status": "accepted",
                "accepted_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Marcar repartidor como no disponible
    await db.socios_repartidores.update_one(
        {"socio_id": repartidor["socio_id"]}, {"$set": {"is_available": False}}
    )

    return {
        "message": "Pedido confirmado y repartidor asignado",
        "order_id": order_id,
        "driver_assigned": True,
        "driver_name": repartidor.get("user_id"),
    }


@router.post("/orders/{order_id}/complete")
async def complete_order(order_id: str, user: dict = Depends(get_current_user)):
    """
    Marcar pedido como completado (entregado).

    ECONOMÍA DESCENTRALIZADA:
    - El cliente ya pagó productos al comercio (efectivo)
    - El cliente ya pagó envío al repartidor (efectivo)
    - Xuve descuenta 12% del total de productos del balance del Socio Comercial
    """
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if order["status"] == "completed":
        raise HTTPException(status_code=400, detail="Este pedido ya fue completado")

    # Actualizar estado del pedido
    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Liberar repartidor
    if order.get("driver_id"):
        await db.socios_repartidores.update_one(
            {"socio_id": order["driver_id"]}, {"$set": {"is_available": True}}
        )

    # COBRAR COMISIÓN AL SOCIO COMERCIAL
    store = await db.socios_comerciales.find_one(
        {"comercial_id": order["store_id"]}, {"_id": 0}
    )
    if not store:
        # Buscar también en market_stores por compatibilidad
        store = await db.market_stores.find_one(
            {"store_id": order["store_id"]}, {"_id": 0}
        )

    if store and store.get("user_id"):
        # Obtener tasa de comisión desde la configuración del admin
        market_commission_rate = await get_commission_rate("market")
        products_total = order.get(
            "products_total", order.get("total_usd", 0) - order.get("delivery_fee", 2.0)
        )
        commission = products_total * market_commission_rate

        # Descontar comisión del balance del comercio
        await db.users.update_one(
            {"user_id": store["user_id"]}, {"$inc": {"wallet_balance": -commission}}
        )

        # Registrar transacción
        await db.transactions.insert_one(
            {
                "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
                "user_id": store["user_id"],
                "amount_usd": -commission,
                "type": TransactionType.COMMISSION_DEDUCTION.value,
                "status": "completed",
                "reference": order_id,
                "description": f"Comisión {int(market_commission_rate*100)}% Market - Pedido #{order_id[-6:]} - Productos ${products_total:.2f}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Actualizar estadísticas del comercio
        await db.socios_comerciales.update_one(
            {"comercial_id": order["store_id"]},
            {"$inc": {"total_orders": 1, "total_revenue": products_total - commission}},
        )

        return {
            "message": "Pedido completado",
            "products_total": products_total,
            "commission_charged": commission,
            "commission_rate": f"{int(market_commission_rate*100)}%",
        }

    return {"message": "Pedido completado (sin comercio asociado para cobrar comisión)"}


@router.get("/orders")
async def get_user_orders(user: dict = Depends(get_current_user)):
    orders = (
        await db.orders.find({"user_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )
    return orders


@router.get("/orders/{order_id}")
async def get_order(order_id: str, user: dict = Depends(get_current_user)):
    order = await db.orders.find_one(
        {"order_id": order_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return order


# ==================== DELIVERY ASSIGNMENTS ====================


@router.get("/delivery/pending")
async def get_pending_deliveries(user: dict = Depends(get_current_user)):
    """
    Obtener pedidos pendientes para repartidores.
    Solo muestra pedidos si el repartidor tiene is_delivery_active = True
    """
    # Verificar que el usuario es repartidor con delivery activo
    repartidor = await db.socios_repartidores.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )

    if not repartidor:
        raise HTTPException(status_code=403, detail="No eres un repartidor registrado")

    if not repartidor.get("is_delivery_active", False):
        return {"message": "Activa el modo Delivery para ver pedidos", "deliveries": []}

    # Buscar pedidos pendientes sin repartidor asignado
    pending_orders = (
        await db.orders.find({"status": "pending", "driver_id": None}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(20)
    )

    return {"deliveries": pending_orders}


@router.post("/delivery/{order_id}/accept")
async def accept_delivery(order_id: str, user: dict = Depends(get_current_user)):
    """Aceptar un pedido de delivery"""
    repartidor = await db.socios_repartidores.find_one(
        {"user_id": user["user_id"], "is_delivery_active": True}, {"_id": 0}
    )

    if not repartidor:
        raise HTTPException(
            status_code=403, detail="Debes activar el modo Delivery primero"
        )

    order = await db.orders.find_one(
        {"order_id": order_id, "driver_id": None}, {"_id": 0}
    )
    if not order:
        raise HTTPException(
            status_code=404, detail="Pedido no encontrado o ya asignado"
        )

    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "driver_id": repartidor["socio_id"],
                "status": "accepted",
                "accepted_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    await db.socios_repartidores.update_one(
        {"socio_id": repartidor["socio_id"]}, {"$set": {"is_available": False}}
    )

    return {"message": "Pedido aceptado", "order_id": order_id}

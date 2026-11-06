"""
OMNI - Rutas de Gestión de Productos para Comercios
===================================================
Sistema robusto con:
- CRUD completo de productos
- Carga masiva por Excel/CSV
- Gestión de múltiples imágenes
- Búsqueda y filtros avanzados
- Categorías y subcategorías
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from utils.auth import get_current_user
from utils.database import db
from models.product_models import (
    ProductCreate,
    ProductUpdate,
    ProductStatus,
    BulkImportResult,
    DEFAULT_CATEGORIES,
)
import uuid
import io
import csv

router = APIRouter(prefix="/store/products", tags=["Store Products"])


def generate_product_id():
    return f"prod_{uuid.uuid4().hex[:12]}"


def generate_image_id():
    return f"img_{uuid.uuid4().hex[:8]}"


# ==================== PRODUCTOS CRUD ====================


@router.get("")
async def get_my_products(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    status: Optional[str] = None,
    has_images: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    user: dict = Depends(get_current_user),
):
    """
    Obtener todos los productos del comercio con filtros y paginación.
    """
    # Obtener store_id del usuario
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    store_id = store["store_id"]

    # Construir query
    query = {"store_id": store_id}

    if category:
        query["category"] = category
    if subcategory:
        query["subcategory"] = subcategory
    if status:
        query["status"] = status
    if has_images is not None:
        if has_images:
            query["images"] = {"$exists": True, "$ne": []}
        else:
            query["$or"] = [{"images": {"$exists": False}}, {"images": []}]
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
            {"barcode": {"$regex": search, "$options": "i"}},
        ]

    # Ordenamiento
    sort_direction = -1 if sort_order == "desc" else 1
    sort_field = (
        sort_by
        if sort_by in ["name", "price", "stock", "created_at", "updated_at"]
        else "created_at"
    )

    # Contar total
    total = await db.market_products.count_documents(query)

    # Obtener productos paginados
    skip = (page - 1) * limit
    products = (
        await db.market_products.find(query, {"_id": 0})
        .sort(sort_field, sort_direction)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )

    # Agregar campos calculados
    for p in products:
        p["has_images"] = len(p.get("images", [])) > 0
        p["images_count"] = len(p.get("images", []))
        p["primary_image_url"] = next(
            (img["url"] for img in p.get("images", []) if img.get("is_primary")),
            p.get("images", [{}])[0].get("url") if p.get("images") else None,
        )

    return {
        "products": products,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        },
    }


@router.get("/stats")
async def get_products_stats(user: dict = Depends(get_current_user)):
    """
    Obtener estadísticas de productos del comercio.
    """
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    store_id = store["store_id"]

    # Estadísticas
    total = await db.market_products.count_documents({"store_id": store_id})
    active = await db.market_products.count_documents(
        {"store_id": store_id, "status": "active", "is_available": True}
    )
    out_of_stock = await db.market_products.count_documents(
        {"store_id": store_id, "stock": 0, "track_inventory": True}
    )
    without_images = await db.market_products.count_documents(
        {"store_id": store_id, "$or": [{"images": {"$exists": False}}, {"images": []}]}
    )

    # Productos por categoría
    pipeline = [
        {"$match": {"store_id": store_id}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    categories = await db.market_products.aggregate(pipeline).to_list(50)

    return {
        "total_products": total,
        "active_products": active,
        "out_of_stock": out_of_stock,
        "without_images": without_images,
        "by_category": [
            {"category": c["_id"], "count": c["count"]} for c in categories
        ],
    }


@router.post("")
async def create_product(
    product: ProductCreate, user: dict = Depends(get_current_user)
):
    """
    Crear un nuevo producto.
    """
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1, "store_name": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    now = datetime.now(timezone.utc).isoformat()

    new_product = {
        "product_id": generate_product_id(),
        "store_id": store["store_id"],
        "store_name": store.get("store_name", ""),
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "compare_at_price": product.compare_at_price,
        "category": product.category,
        "subcategory": product.subcategory,
        "sku": product.sku,
        "barcode": product.barcode,
        "stock": product.stock,
        "track_inventory": product.track_inventory,
        "is_available": product.is_available,
        "available": product.is_available,  # Compatibilidad
        "status": ProductStatus.ACTIVE if product.is_available else ProductStatus.DRAFT,
        "images": [],
        "variants": [v.dict() for v in product.variants] if product.variants else [],
        "tags": product.tags,
        "created_at": now,
        "updated_at": now,
        "created_by": user.get("user_id"),
    }

    await db.market_products.insert_one(new_product)
    new_product.pop("_id", None)

    return {"message": "Producto creado", "product": new_product}


@router.get("/{product_id}")
async def get_product(product_id: str, user: dict = Depends(get_current_user)):
    """
    Obtener un producto específico.
    """
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    product = await db.market_products.find_one(
        {"product_id": product_id, "store_id": store["store_id"]}, {"_id": 0}
    )

    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    return product


@router.put("/{product_id}")
async def update_product(
    product_id: str, updates: ProductUpdate, user: dict = Depends(get_current_user)
):
    """
    Actualizar un producto.
    """
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    # Verificar que el producto existe
    product = await db.market_products.find_one(
        {"product_id": product_id, "store_id": store["store_id"]}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Preparar actualizaciones
    update_data = {k: v for k, v in updates.dict().items() if v is not None}
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Sincronizar is_available con available (compatibilidad)
        if "is_available" in update_data:
            update_data["available"] = update_data["is_available"]

        await db.market_products.update_one(
            {"product_id": product_id}, {"$set": update_data}
        )

    updated = await db.market_products.find_one({"product_id": product_id}, {"_id": 0})
    return {"message": "Producto actualizado", "product": updated}


@router.delete("/{product_id}")
async def delete_product(product_id: str, user: dict = Depends(get_current_user)):
    """
    Eliminar un producto.
    """
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    result = await db.market_products.delete_one(
        {"product_id": product_id, "store_id": store["store_id"]}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    return {"message": "Producto eliminado", "product_id": product_id}


# ==================== IMÁGENES ====================


@router.post("/{product_id}/images")
async def add_product_image(
    product_id: str,
    image_url: str,
    is_primary: bool = False,
    alt_text: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """
    Agregar una imagen a un producto.
    """
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    product = await db.market_products.find_one(
        {"product_id": product_id, "store_id": store["store_id"]}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    images = product.get("images", [])

    # Si es primary, quitar el primary de las demás
    if is_primary:
        for img in images:
            img["is_primary"] = False

    # Si no hay imágenes, esta será la primary
    if not images:
        is_primary = True

    new_image = {
        "image_id": generate_image_id(),
        "url": image_url,
        "alt_text": alt_text or product.get("name", ""),
        "is_primary": is_primary,
        "order": len(images),
    }

    images.append(new_image)

    await db.market_products.update_one(
        {"product_id": product_id},
        {
            "$set": {
                "images": images,
                "image_url": (
                    new_image["url"]
                    if is_primary
                    else product.get("image_url", new_image["url"])
                ),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": "Imagen agregada", "image": new_image}


@router.delete("/{product_id}/images/{image_id}")
async def remove_product_image(
    product_id: str, image_id: str, user: dict = Depends(get_current_user)
):
    """
    Eliminar una imagen de un producto.
    """
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    product = await db.market_products.find_one(
        {"product_id": product_id, "store_id": store["store_id"]}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    images = [img for img in product.get("images", []) if img["image_id"] != image_id]

    # Si se eliminó la primary, hacer primary la primera
    if images and not any(img.get("is_primary") for img in images):
        images[0]["is_primary"] = True

    primary_url = next((img["url"] for img in images if img.get("is_primary")), None)

    await db.market_products.update_one(
        {"product_id": product_id},
        {
            "$set": {
                "images": images,
                "image_url": primary_url,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": "Imagen eliminada"}


@router.put("/{product_id}/images/{image_id}/primary")
async def set_primary_image(
    product_id: str, image_id: str, user: dict = Depends(get_current_user)
):
    """
    Establecer una imagen como principal.
    """
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    product = await db.market_products.find_one(
        {"product_id": product_id, "store_id": store["store_id"]}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    images = product.get("images", [])
    primary_url = None

    for img in images:
        if img["image_id"] == image_id:
            img["is_primary"] = True
            primary_url = img["url"]
        else:
            img["is_primary"] = False

    await db.market_products.update_one(
        {"product_id": product_id},
        {
            "$set": {
                "images": images,
                "image_url": primary_url,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": "Imagen principal actualizada"}


# ==================== IMPORTACIÓN MASIVA ====================


@router.get("/import/template")
async def get_import_template(user: dict = Depends(get_current_user)):
    """
    Descargar plantilla de Excel/CSV para importación masiva.
    """
    # Crear CSV de ejemplo
    output = io.StringIO()
    writer = csv.writer(output)

    # Encabezados
    headers = [
        "nombre",
        "descripcion",
        "precio",
        "precio_anterior",
        "categoria",
        "subcategoria",
        "sku",
        "codigo_barras",
        "stock",
        "disponible",
        "etiquetas",
    ]
    writer.writerow(headers)

    # Filas de ejemplo
    examples = [
        [
            "Acetaminofén 500mg",
            "Analgésico y antipirético",
            "2.50",
            "",
            "Medicamentos",
            "Sin receta",
            "MED001",
            "7501234567890",
            "100",
            "si",
            "dolor,fiebre",
        ],
        [
            "Ibuprofeno 400mg",
            "Antiinflamatorio",
            "3.00",
            "3.50",
            "Medicamentos",
            "Sin receta",
            "MED002",
            "7501234567891",
            "50",
            "si",
            "dolor,inflamacion",
        ],
        [
            "Shampoo Anticaspa",
            "Shampoo medicado 200ml",
            "5.99",
            "",
            "Cuidado Personal",
            "Cabello",
            "CP001",
            "",
            "30",
            "si",
            "cabello,caspa",
        ],
    ]
    for row in examples:
        writer.writerow(row)

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=plantilla_productos_omni.csv"
        },
    )


@router.post("/import/csv")
async def import_products_csv(
    file: UploadFile = File(...),
    update_existing: bool = False,
    user: dict = Depends(get_current_user),
):
    """
    Importar productos desde archivo CSV.

    Columnas esperadas:
    - nombre (requerido)
    - descripcion
    - precio (requerido)
    - precio_anterior
    - categoria (requerido)
    - subcategoria
    - sku
    - codigo_barras
    - stock
    - disponible (si/no)
    - etiquetas (separadas por coma)
    """
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1, "store_name": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    store_id = store["store_id"]
    store_name = store.get("store_name", "")

    # Leer archivo
    try:
        content = await file.read()
        # Intentar decodificar con diferentes encodings
        for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            try:
                text = content.decode(encoding)
                break
            except:
                continue
        else:
            raise HTTPException(
                status_code=400, detail="No se pudo decodificar el archivo"
            )

        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {str(e)}")

    if not rows:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    result = BulkImportResult(
        total_rows=len(rows), successful=0, failed=0, errors=[], products_created=[]
    )

    now = datetime.now(timezone.utc).isoformat()

    for idx, row in enumerate(rows, start=2):  # Start at 2 (row 1 is header)
        try:
            # Limpiar keys (quitar espacios y convertir a minúsculas), ignorar keys None
            row = {
                k.strip().lower().replace(" ", "_"): v.strip() if v else ""
                for k, v in row.items()
                if k is not None
            }

            # Validar campos requeridos
            name = row.get("nombre", "")
            price_str = row.get("precio", "")
            category = row.get("categoria", "")

            if not name:
                result.errors.append({"row": idx, "error": "Nombre es requerido"})
                result.failed += 1
                continue

            if not price_str:
                result.errors.append({"row": idx, "error": "Precio es requerido"})
                result.failed += 1
                continue

            try:
                price = float(price_str.replace(",", ".").replace("$", "").strip())
            except:
                result.errors.append(
                    {"row": idx, "error": f"Precio inválido: {price_str}"}
                )
                result.failed += 1
                continue

            if not category:
                category = "General"

            # Verificar si existe (por SKU o nombre)
            sku = row.get("sku", "")
            existing = None
            if sku:
                existing = await db.market_products.find_one(
                    {"store_id": store_id, "sku": sku}
                )
            if not existing:
                existing = await db.market_products.find_one(
                    {"store_id": store_id, "name": name}
                )

            if existing and not update_existing:
                result.errors.append(
                    {
                        "row": idx,
                        "error": f"Producto ya existe: {name}",
                        "skipped": True,
                    }
                )
                result.failed += 1
                continue

            # Preparar datos
            compare_price_str = row.get("precio_anterior", "")
            try:
                compare_price = (
                    float(compare_price_str.replace(",", ".").replace("$", "").strip())
                    if compare_price_str
                    else None
                )
            except:
                compare_price = None

            stock_str = row.get("stock", "0")
            try:
                stock = int(float(stock_str))
            except:
                stock = 0

            disponible = row.get("disponible", "si").lower() in [
                "si",
                "sí",
                "yes",
                "1",
                "true",
                "activo",
            ]

            tags_str = row.get("etiquetas", "")
            tags = (
                [t.strip() for t in tags_str.split(",") if t.strip()]
                if tags_str
                else []
            )

            product_data = {
                "name": name,
                "description": row.get("descripcion", ""),
                "price": price,
                "compare_at_price": compare_price,
                "category": category,
                "subcategory": row.get("subcategoria", ""),
                "sku": sku,
                "barcode": row.get("codigo_barras", ""),
                "stock": stock,
                "track_inventory": True,
                "is_available": disponible,
                "available": disponible,
                "status": "active" if disponible else "draft",
                "tags": tags,
                "updated_at": now,
            }

            if existing and update_existing:
                # Actualizar existente
                await db.market_products.update_one(
                    {"product_id": existing["product_id"]}, {"$set": product_data}
                )
                result.products_created.append(existing["product_id"])
            else:
                # Crear nuevo
                product_data.update(
                    {
                        "product_id": generate_product_id(),
                        "store_id": store_id,
                        "store_name": store_name,
                        "images": [],
                        "variants": [],
                        "created_at": now,
                        "created_by": user.get("user_id"),
                    }
                )
                await db.market_products.insert_one(product_data)
                result.products_created.append(product_data["product_id"])

            result.successful += 1

        except Exception as e:
            result.errors.append({"row": idx, "error": str(e)})
            result.failed += 1

    return result


@router.post("/import/preview")
async def preview_import(
    file: UploadFile = File(...), user: dict = Depends(get_current_user)
):
    """
    Vista previa de importación (primeras 10 filas).
    """
    try:
        content = await file.read()
        for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            try:
                text = content.decode(encoding)
                break
            except:
                continue

        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for i, row in enumerate(reader):
            if i >= 10:
                break
            rows.append({k.strip(): v.strip() if v else "" for k, v in row.items()})

        return {
            "headers": list(rows[0].keys()) if rows else [],
            "preview_rows": rows,
            "total_rows": sum(1 for _ in csv.DictReader(io.StringIO(text))),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {str(e)}")


# ==================== CATEGORÍAS ====================


@router.get("/categories/list")
async def get_categories(
    store_type: str = "general", user: dict = Depends(get_current_user)
):
    """
    Obtener categorías predefinidas según el tipo de tienda.
    """
    categories = DEFAULT_CATEGORIES.get(store_type, DEFAULT_CATEGORIES["general"])
    return {"categories": categories, "store_type": store_type}


@router.get("/categories/my-store")
async def get_my_store_categories(user: dict = Depends(get_current_user)):
    """
    Obtener categorías usadas en mi tienda.
    """
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    pipeline = [
        {"$match": {"store_id": store["store_id"]}},
        {
            "$group": {
                "_id": {"category": "$category", "subcategory": "$subcategory"},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1}},
    ]

    results = await db.market_products.aggregate(pipeline).to_list(100)

    # Agrupar por categoría
    categories = {}
    for r in results:
        cat = r["_id"]["category"]
        subcat = r["_id"]["subcategory"]
        if cat not in categories:
            categories[cat] = {"name": cat, "count": 0, "subcategories": []}
        categories[cat]["count"] += r["count"]
        if subcat and subcat not in [
            s["name"] for s in categories[cat]["subcategories"]
        ]:
            categories[cat]["subcategories"].append(
                {"name": subcat, "count": r["count"]}
            )

    return {"categories": list(categories.values())}


# ==================== ACCIONES MASIVAS ====================


class BulkAvailabilityUpdate(BaseModel):
    product_ids: List[str]
    is_available: bool


@router.post("/bulk/update-availability")
async def bulk_update_availability(
    data: BulkAvailabilityUpdate, user: dict = Depends(get_current_user)
):
    """
    Actualizar disponibilidad de múltiples productos.
    """
    product_ids = data.product_ids
    is_available = data.is_available

    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    result = await db.market_products.update_many(
        {"product_id": {"$in": product_ids}, "store_id": store["store_id"]},
        {
            "$set": {
                "is_available": is_available,
                "available": is_available,
                "status": "active" if is_available else "inactive",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": f"{result.modified_count} productos actualizados"}


class BulkDeleteRequest(BaseModel):
    product_ids: List[str]


@router.post("/bulk/delete")
async def bulk_delete_products(
    data: BulkDeleteRequest, user: dict = Depends(get_current_user)
):
    """
    Eliminar múltiples productos.
    """
    product_ids = data.product_ids
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    result = await db.market_products.delete_many(
        {"product_id": {"$in": product_ids}, "store_id": store["store_id"]}
    )

    return {"message": f"{result.deleted_count} productos eliminados"}


@router.post("/bulk/update-stock")
async def bulk_update_stock(
    updates: List[dict],  # [{"product_id": "xxx", "stock": 10}, ...]
    user: dict = Depends(get_current_user),
):
    """
    Actualizar stock de múltiples productos.
    """
    store = await db.store_profiles.find_one(
        {"user_id": user.get("user_id")}, {"_id": 0, "store_id": 1}
    )
    if not store:
        raise HTTPException(status_code=404, detail="No tienes una tienda registrada")

    updated_count = 0
    now = datetime.now(timezone.utc).isoformat()

    for update in updates:
        product_id = update.get("product_id")
        stock = update.get("stock", 0)

        result = await db.market_products.update_one(
            {"product_id": product_id, "store_id": store["store_id"]},
            {"$set": {"stock": stock, "updated_at": now}},
        )
        if result.modified_count:
            updated_count += 1

    return {"message": f"{updated_count} productos actualizados"}

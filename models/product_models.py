"""
Xuve - Modelos de Productos para Comercios
==========================================
Sistema robusto de gestión de productos con:
- Múltiples imágenes por producto
- Categorías y subcategorías
- SKU/Código de barras
- Control de inventario
- Variantes (tallas, colores, etc.)
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ProductStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    DRAFT = "draft"


class ProductVariant(BaseModel):
    """Variante de producto (ej: talla, color, presentación)"""

    variant_id: str
    name: str  # "500ml", "1L", "Caja x 10"
    price: float
    stock: int = 0
    sku: Optional[str] = None
    is_available: bool = True


class ProductImage(BaseModel):
    """Imagen de producto"""

    image_id: str
    url: str
    alt_text: Optional[str] = None
    is_primary: bool = False
    order: int = 0


class ProductCreate(BaseModel):
    """Modelo para crear un producto"""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    price: float = Field(..., gt=0)
    compare_at_price: Optional[float] = None  # Precio anterior (para mostrar descuento)
    category: str = Field(..., min_length=1)
    subcategory: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    stock: int = Field(default=0, ge=0)
    track_inventory: bool = True
    is_available: bool = True
    tags: List[str] = []
    variants: List[ProductVariant] = []


class ProductUpdate(BaseModel):
    """Modelo para actualizar un producto"""

    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    compare_at_price: Optional[float] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    stock: Optional[int] = None
    track_inventory: Optional[bool] = None
    is_available: Optional[bool] = None
    status: Optional[ProductStatus] = None
    tags: Optional[List[str]] = None


class ProductFull(BaseModel):
    """Modelo completo de producto"""

    product_id: str
    store_id: str
    name: str
    description: Optional[str] = None
    price: float
    compare_at_price: Optional[float] = None
    category: str
    subcategory: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    stock: int = 0
    track_inventory: bool = True
    is_available: bool = True
    status: ProductStatus = ProductStatus.ACTIVE
    images: List[ProductImage] = []
    variants: List[ProductVariant] = []
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime
    created_by: str

    # Campos calculados
    has_images: bool = False
    images_count: int = 0
    primary_image_url: Optional[str] = None


class BulkImportResult(BaseModel):
    """Resultado de importación masiva"""

    total_rows: int
    successful: int
    failed: int
    errors: List[dict] = []
    products_created: List[str] = []


class ProductCategory(BaseModel):
    """Categoría de productos"""

    category_id: str
    name: str
    icon: Optional[str] = None
    subcategories: List[str] = []
    products_count: int = 0


# Categorías predefinidas para farmacias y comercios
DEFAULT_CATEGORIES = {
    "farmacia": [
        {
            "name": "Medicamentos",
            "icon": "💊",
            "subcategories": ["Con receta", "Sin receta", "Genéricos", "De marca"],
        },
        {
            "name": "Cuidado Personal",
            "icon": "🧴",
            "subcategories": [
                "Higiene",
                "Cuidado facial",
                "Cuidado corporal",
                "Cabello",
            ],
        },
        {
            "name": "Bebés y Niños",
            "icon": "👶",
            "subcategories": ["Pañales", "Alimentación", "Cuidado", "Juguetes"],
        },
        {
            "name": "Vitaminas y Suplementos",
            "icon": "💪",
            "subcategories": ["Vitaminas", "Minerales", "Proteínas", "Naturales"],
        },
        {
            "name": "Primeros Auxilios",
            "icon": "🩹",
            "subcategories": ["Vendajes", "Antisépticos", "Termómetros", "Equipos"],
        },
        {
            "name": "Belleza",
            "icon": "💄",
            "subcategories": ["Maquillaje", "Perfumes", "Uñas", "Accesorios"],
        },
        {
            "name": "Equipos Médicos",
            "icon": "🏥",
            "subcategories": [
                "Monitores",
                "Nebulizadores",
                "Sillas de ruedas",
                "Otros",
            ],
        },
    ],
    "restaurante": [
        {
            "name": "Entradas",
            "icon": "🥗",
            "subcategories": ["Ensaladas", "Sopas", "Aperitivos"],
        },
        {
            "name": "Platos Principales",
            "icon": "🍽️",
            "subcategories": ["Carnes", "Pollo", "Pescados", "Vegetarianos"],
        },
        {
            "name": "Bebidas",
            "icon": "🥤",
            "subcategories": ["Refrescos", "Jugos", "Calientes", "Alcohólicas"],
        },
        {
            "name": "Postres",
            "icon": "🍰",
            "subcategories": ["Tortas", "Helados", "Frutas"],
        },
        {
            "name": "Combos",
            "icon": "🍱",
            "subcategories": ["Individuales", "Familiares", "Especiales"],
        },
    ],
    "supermercado": [
        {
            "name": "Frutas y Verduras",
            "icon": "🥬",
            "subcategories": ["Frutas", "Verduras", "Orgánicos"],
        },
        {
            "name": "Carnes y Pescados",
            "icon": "🥩",
            "subcategories": ["Res", "Pollo", "Cerdo", "Pescados", "Mariscos"],
        },
        {
            "name": "Lácteos",
            "icon": "🥛",
            "subcategories": ["Leche", "Quesos", "Yogurt", "Mantequilla"],
        },
        {
            "name": "Panadería",
            "icon": "🥖",
            "subcategories": ["Pan", "Dulces", "Tortas"],
        },
        {
            "name": "Bebidas",
            "icon": "🧃",
            "subcategories": ["Agua", "Refrescos", "Jugos", "Cervezas"],
        },
        {
            "name": "Limpieza",
            "icon": "🧹",
            "subcategories": ["Hogar", "Ropa", "Personal"],
        },
    ],
    "general": [
        {"name": "Productos", "icon": "📦", "subcategories": ["General"]},
    ],
}

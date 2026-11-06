"""
Xuve SuperApp API v2.0 - Beta Estructural
==========================================
Clean, modular FastAPI server.
All models are in /models/ and endpoints in /routes/
"""

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

# Add backend directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import init_db, close_db
from models.user_models import VALID_ROLES

# Rate limiting (instancia compartida en utils/ratelimit.py)
from slowapi.middleware import SlowAPIMiddleware
from utils.ratelimit import limiter

# Import all routers
from routes.auth_routes import router as auth_router
from routes.wallet_routes import router as wallet_router, exchange_router
from routes.socio_routes import router as socio_router
from routes.service_routes import router as service_router, ratings_router
from routes.market_routes import router as market_router
from routes.rent_routes import router as rent_router
from routes.driver_routes import router as driver_router
from routes.admin_routes import router as admin_router
from routes.routes_routes import router as routes_router
from routes.user_routes import router as user_router
from routes.seed_routes import router as seed_router
from routes.upload_routes import router as upload_router, uploads_router
from routes.carga_routes import router as carga_router
from routes.line_routes import (
    router as line_router,
)  # B2B Líneas de Transporte Interurbano
from routes.rutas_urbanas_routes import (
    router as rutas_urbanas_router,
)  # Rutas Urbanas (legacy line_admin)
from routes.urban_line_routes import (
    router as urban_line_router,
)  # Líneas de Transporte Urbano (urban_line_admin)
from routes.comercial_category_routes import (
    router as comercial_category_router,
)  # Categorías Comercios
from routes.comercial_orders_routes import (
    router as comercial_orders_router,
)  # Pedidos Comercial
from routes.kyc_routes import router as kyc_router  # KYC Modular
from routes.chat_routes import router as chat_router  # Chat Operativo
from routes.notification_routes import router as notification_router  # Notificaciones
from routes.subscription_routes import (
    router as subscription_router,
)  # Sistema de Suscripción Diaria
from routes.product_routes import (
    router as product_router,
)  # Gestión de Productos para Comercios
from routes.prescription_routes import router as prescription_router  # Recetas Médicas
from routes.interurbano_routes import (
    router as interurbano_router,
)  # Transporte Interurbano
from routes.geo_routes import router as geo_router  # Proxy Google Maps (server-side key)
from routes.payment_routes import router as payment_router  # Suscripción SaaS $1/día
from routes.payment_method_routes import (
    router as payment_method_router,
)  # KYC progresivo: titularidad de métodos de pago (xuve-kyc-service)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Xuve SuperApp API", version="2.0")

# Rate limiting: misma instancia que usan los decoradores por ruta.
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Include all routers under /api prefix
app.include_router(auth_router, prefix="/api")
app.include_router(wallet_router, prefix="/api")
app.include_router(exchange_router, prefix="/api")
app.include_router(socio_router, prefix="/api")
app.include_router(service_router, prefix="/api")
app.include_router(ratings_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(rent_router, prefix="/api")
app.include_router(driver_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(routes_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(seed_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")  # Static file serving
app.include_router(carga_router, prefix="/api")  # Carga Pesada
app.include_router(line_router, prefix="/api")  # B2B Líneas de Transporte Interurbano
app.include_router(
    rutas_urbanas_router, prefix="/api"
)  # Rutas Urbanas (legacy line_admin)
app.include_router(
    urban_line_router, prefix="/api"
)  # Líneas de Transporte Urbano (nuevo rol)
app.include_router(comercial_category_router, prefix="/api")  # Categorías Comercios
app.include_router(comercial_orders_router, prefix="/api")  # Pedidos Comercial
app.include_router(kyc_router, prefix="/api")  # KYC Modular
app.include_router(chat_router, prefix="/api")  # Chat Operativo
app.include_router(notification_router, prefix="/api")  # Notificaciones
app.include_router(subscription_router, prefix="/api")  # Sistema de Suscripción Diaria
app.include_router(product_router, prefix="/api")  # Gestión de Productos
app.include_router(prescription_router, prefix="/api")  # Recetas Médicas
app.include_router(interurbano_router, prefix="/api")  # Transporte Interurbano
app.include_router(geo_router, prefix="/api")  # Proxy Google Maps (server-side key)
app.include_router(payment_router, prefix="/api")  # Suscripción SaaS $1/día
# Métodos de pago con validación de titularidad (KYC progresivo). Se monta bajo
# /api/v1 según el contrato con la app móvil: /api/v1/user/payment-methods
app.include_router(payment_method_router, prefix="/api/v1")


# Root endpoint
@app.get("/api/")
async def root():
    return {
        "message": "Xuve SuperApp API v2.0 - Beta Estructural",
        "status": "online",
        "roles": VALID_ROLES,
        "architecture": "Modular (FastAPI Best Practices)",
    }


# Health check endpoint for Kubernetes probes
@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup event: inicializa el pool de PostgreSQL y crea el esquema
@app.on_event("startup")
async def startup_db_client():
    await init_db()


# Shutdown event
@app.on_event("shutdown")
async def shutdown_db_client():
    await close_db()

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional
from datetime import datetime

# ROLES DEL SISTEMA:
# user - Usuario/Cliente Final (también actúa como paciente)
# socio_conductor - Socio Conductor (Movilidad Urbana: carros, taxis, mototaxis)
# socio_repartidor - Socio Repartidor (Micromovilidad: bicicletas, monopatines, motos delivery)
# socio_comercial - Socio Comercial (Tiendas: restaurantes, farmacias, supermercados)
# rent_owner - Propietario Rent a Car
# carga_pesada - Operador Carga Pesada (Fletes, mudanzas, cisternas)
# line_admin - Administrador de Terminal/Línea Interurbana (B2B viajes programados)
# chofer_linea - Chofer afiliado a una Línea de Transporte Interurbana
# medico - Médico (recetas digitales enviadas a Farmabien)
# admin - Administrador

VALID_ROLES = [
    "user",
    "socio_conductor",
    "socio_repartidor",
    "socio_comercial",
    "rent_owner",
    "carga_pesada",
    "line_admin",
    "chofer_linea",
    "transporte_interurbano",
    "urban_line_admin",
    "chofer_urbano",
    "medico",
    "admin",
]

# Roles que SÍ se pueden obtener vía KYC. Nunca incluye "admin" (no se concede
# por KYC) ni "user" (rol base). Se usa como whitelist al solicitar y al aprobar.
KYC_ELEVATABLE_ROLES = {r for r in VALID_ROLES if r not in ("admin", "user")}

CONDUCTOR_VEHICLE_TYPES = ["carro_particular", "taxi_linea", "mototaxi"]
REPARTIDOR_VEHICLE_TYPES = ["bicicleta", "monopatín_electrico", "moto_delivery"]
CARGA_VEHICLE_TYPES = ["camion_350", "camion_750", "camion_cava", "cisterna"]
# Tipos de vehículos para Líneas de Transporte B2B
LINE_VEHICLE_TYPES = ["buseta", "van", "expreso", "minibus", "autobus"]
# Tipos de servicio de línea
LINE_SERVICE_TYPES = [
    "interurbano",
    "urbano",
]  # interurbano = terminales, urbano = rutas fijas QR


# Roles que un usuario puede SOLICITAR al registrarse. El registro nunca asigna
# directamente un rol de socio/admin: el rol efectivo siempre nace como "user" y
# solo se eleva tras aprobación de KYC. Cualquier rol distinto de "user" que se
# envíe en el registro se guarda como `pending_role` (intención), nunca como rol.
SELF_REGISTRABLE_ROLE = "user"
PRIVILEGED_ROLES = {"admin"}


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str
    phone: str
    role: str = "user"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class VerifyEmail(BaseModel):
    email: EmailStr
    code: str


class ResendVerification(BaseModel):
    email: EmailStr


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    password: str = Field(min_length=8)


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    phone: Optional[str] = None
    picture: Optional[str] = None
    role: str = "user"
    sub_role: Optional[str] = None
    wallet_balance: float = 0.0
    wallet_held: float = 0.0
    status: str = "active"
    kyc_status: str = "pending"
    avg_rating: float = 5.0
    total_trips: int = 0
    created_at: datetime


class KYCConductor(BaseModel):
    """KYC para Socio Conductor - Requiere todos los documentos"""

    cedula_url: str
    cedula_number: str
    license_url: str
    license_category: str
    medical_card_url: str
    medical_card_expiry: str
    circulation_card_url: str
    rcv_insurance_url: str
    rcv_expiry: str
    vehicle_photo_url: str


class KYCRepartidor(BaseModel):
    """KYC para Socio Repartidor - Documentos según vehículo"""

    cedula_url: str
    cedula_number: str
    frontal_photo_url: str
    license_url: Optional[str] = None
    circulation_card_url: Optional[str] = None


class SocioConductorRegister(BaseModel):
    """Registro de Socio Conductor (Movilidad Urbana)"""

    vehicle_type: str
    cedula_url: str
    cedula_number: str
    license_url: str
    license_category: str
    medical_card_url: str
    circulation_card_url: str
    rcv_insurance_url: str
    plate_number: str
    vehicle_brand: str
    vehicle_model: str
    vehicle_year: int
    vehicle_color: str
    vehicle_photo_url: str
    taxi_line_name: Optional[str] = None
    taxi_line_permit: Optional[str] = None


class SocioRepartidorRegister(BaseModel):
    """Registro de Socio Repartidor (Micromovilidad/Delivery)"""

    vehicle_type: str
    cedula_url: str
    cedula_number: str
    frontal_photo_url: str
    license_url: Optional[str] = None
    circulation_card_url: Optional[str] = None
    plate_number: Optional[str] = None
    vehicle_brand: Optional[str] = None
    vehicle_model: Optional[str] = None

"""
Validaciones de Entrada de los Controladores (Pydantic Request/Response Validators).
Todas las validaciones de datos de formularios y payloads HTTP viven en la capa
de Controladores (`controllers/`), manteniendo `models/` exclusivo para Modelos SQL.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum

from models.user_models import (
    VALID_ROLES,
    KYC_ELEVATABLE_ROLES,
    CONDUCTOR_VEHICLE_TYPES,
    REPARTIDOR_VEHICLE_TYPES,
    CARGA_VEHICLE_TYPES,
    LINE_VEHICLE_TYPES,
    LINE_SERVICE_TYPES,
    SELF_REGISTRABLE_ROLE,
    PRIVILEGED_ROLES,
)
from models.wallet_models import (
    TransactionType,
)
from models.service_models import ServiceType, ServiceStatus
from models.product_models import ProductStatus
from models.kyc_models import KYCStatus, LicenseGrade, KYC_ROLE_TYPES, VEHICLE_CATEGORIES
from models.line_models import LineServiceType, LineStatus, VehicleStatus, ChoferStatus
from models.urban_line_models import UrbanLineStatus
from models.payment_method_models import (
    PAYMENT_METHOD_TYPES,
    PAYMENT_METHOD_ACTIVE,
    PAYMENT_METHOD_PENDING,
    ACCOUNT_SUSPENDED_PENDING_REVIEW,
    mask_identifier,
)


# ===========================================================================
# VALIDACIONES DE AUTENTICACIÓN Y USUARIOS (auth_controller / socio_controller)
# ===========================================================================

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str
    phone: Optional[str] = None
    role: str = "user"


class VerifyEmail(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class ResendVerification(BaseModel):
    email: EmailStr


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str = Field(min_length=16)
    new_password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class KYCConductor(BaseModel):
    cedula_url: str
    cedula_number: str
    license_url: str
    license_category: str
    medical_card_url: str
    medical_card_expiry: str
    circulation_card_url: str
    vehicle_type: str
    plate_number: str
    vehicle_brand: str
    vehicle_model: str
    vehicle_year: int
    vehicle_color: str
    vehicle_photo_url: Optional[str] = None
    is_owner: bool = True
    owner_name: Optional[str] = None
    owner_cedula: Optional[str] = None
    owner_phone: Optional[str] = None
    authorization_url: Optional[str] = None


class KYCRepartidor(BaseModel):
    cedula_url: str
    cedula_number: str
    selfie_url: str
    vehicle_type: str
    vehicle_brand: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_color: Optional[str] = None
    vehicle_photo_url: Optional[str] = None
    license_url: Optional[str] = None
    circulation_card_url: Optional[str] = None
    plate_number: Optional[str] = None


class SocioConductorRegister(BaseModel):
    kyc: KYCConductor


class SocioRepartidorRegister(BaseModel):
    kyc: KYCRepartidor


# ===========================================================================
# VALIDACIONES DE BILLETERA (wallet_controller)
# ===========================================================================

class WalletRecharge(BaseModel):
    amount_bs: float
    payment_method: str
    reference: str


class WalletWithdraw(BaseModel):
    amount_usd: float
    bank_name: str
    phone: str
    cedula: str


class WalletHold(BaseModel):
    amount_usd: float
    reason: str
    reference_id: str


# ===========================================================================
# VALIDACIONES DE SERVICIOS Y VIAJES (service_controller)
# ===========================================================================

class Location(BaseModel):
    lat: float
    lng: float
    address: Optional[str] = None


class ServiceRequest(BaseModel):
    service_type: str
    pickup_lat: float
    pickup_lng: float
    pickup_address: str
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None
    dropoff_address: Optional[str] = None
    vehicle_preference: Optional[str] = None
    payment_method: Optional[str] = None
    estimated_fare: Optional[float] = None
    route_id: Optional[str] = None
    notes: Optional[str] = None


class ProviderAvailability(BaseModel):
    is_online: bool
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None


class MatchResult(BaseModel):
    driver_id: str
    user_id: str
    name: str
    vehicle_type: str
    distance_km: float
    eta_minutes: int
    rating: float


class RatingCreate(BaseModel):
    service_id: str
    stars: int
    comment: Optional[str] = None


class Message(BaseModel):
    message_id: str
    service_id: str
    sender_id: str
    sender_name: str
    sender_role: str
    content: str
    message_type: str = "text"
    created_at: str


# ===========================================================================
# VALIDACIONES DE MARKET Y COMERCIOS (market_controller / comercial_category_controller)
# ===========================================================================

class CartItem(BaseModel):
    product_id: str
    quantity: int


class OrderCreate(BaseModel):
    store_id: str
    items: List[CartItem]
    delivery_lat: float
    delivery_lng: float
    delivery_address: str


class ComercialRegister(BaseModel):
    store_name: str
    category: str
    rif: str
    address: str
    lat: float
    lng: float
    phone: str
    opening_hours: str
    image_url: Optional[str] = None


class StoreProfileCreate(BaseModel):
    business_name: str
    category: str  # slug validado contra xuve.business_categories
    rif: str
    description: Optional[str] = None
    address: str
    lat: float
    lng: float
    phone: str
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    horario_apertura: str = "08:00"
    horario_cierre: str = "20:00"
    dias_operacion: List[str] = [
        "lunes", "martes", "miercoles", "jueves", "viernes", "sabado"
    ]
    acepta_efectivo: bool = True
    acepta_pago_movil: bool = True
    acepta_wallet: bool = True
    tiempo_preparacion_min: int = 30
    pedido_minimo_usd: float = 0.0
    radio_entrega_km: float = 10.0


class CategoryListResponse(BaseModel):
    code: str
    name: str
    description: str
    icon: str
    requires_special_docs: List[str]
    allows_prescription: bool
    suggested_product_categories: List[str]


# ===========================================================================
# VALIDACIONES DE CONDUCTORES, RENT, CHAT Y RECETAS
# ===========================================================================

class DriverRegister(BaseModel):
    user_id: str
    vehicle_type: str
    is_owner: bool
    cedula_url: Optional[str] = None
    license_url: Optional[str] = None
    medical_card_url: Optional[str] = None
    owner_cedula: Optional[str] = None
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    plate_number: str
    vehicle_brand: str
    vehicle_model: str


class RentVehicleCreate(BaseModel):
    brand: str
    model: str
    year: int
    color: str
    plate_number: str
    price_per_day_usd: float
    deposit_usd: float
    description: str
    features: List[str] = []
    image_urls: List[str] = []
    lat: float
    lng: float
    address: str


class ChatMessageCreate(BaseModel):
    service_id: str
    content: str
    message_type: str = "text"


class PrescriptionMedication(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str
    quantity: int = 1
    notes: Optional[str] = None


class PrescriptionCreate(BaseModel):
    patient_id: str
    patient_name: str
    patient_cedula: str
    diagnosis: str
    medications: List[PrescriptionMedication]
    general_instructions: Optional[str] = None
    valid_days: int = 30


class PrescriptionUpdate(BaseModel):
    status: str
    pharmacy_id: Optional[str] = None
    dispensed_notes: Optional[str] = None


class PaymentMethodPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_type: str = Field(min_length=1, max_length=32)
    holder_full_name: Optional[str] = Field(default=None, max_length=160)
    holder_id_number: Optional[str] = Field(default=None, max_length=32)
    bank_code: Optional[str] = Field(default=None, max_length=8)
    phone_number: Optional[str] = Field(default=None, max_length=24)
    account_number: Optional[str] = Field(default=None, max_length=34)
    zelle_identifier: Optional[str] = Field(default=None, max_length=160)
    binance_pay_id: Optional[str] = Field(default=None, max_length=24)

    def to_service_payload(self) -> dict:
        return self.model_dump(exclude_none=True)

# ===========================================================================
# VALIDACIONES DE KYC, LÍNEAS, TRANSPORTE URBANO Y PRODUCTOS
# ===========================================================================

class PersonalData(BaseModel):
    """Datos personales básicos"""

    cedula_number: str = Field(..., description="Número de cédula (V-12345678)")
    cedula_front_url: str = Field(..., description="Foto frontal de la cédula")
    cedula_back_url: Optional[str] = Field(
        None, description="Foto reverso de la cédula"
    )
    selfie_url: Optional[str] = Field(None, description="Selfie con cédula visible")
    address: Optional[str] = Field(None, description="Dirección de residencia")


class DriverLicenseData(BaseModel):
    """Datos de licencia de conducir"""

    license_url: str = Field(..., description="Foto de la licencia")
    license_number: str = Field(..., description="Número de licencia")
    license_grade: LicenseGrade = Field(
        ..., description="Grado de licencia (2da, 3ra, 5ta)"
    )
    license_expiry: Optional[str] = Field(None, description="Fecha de vencimiento")


class MedicalData(BaseModel):
    """Certificado médico vial (obligatorio para 5ta)"""

    medical_certificate_url: str = Field(..., description="Foto del certificado médico")
    medical_expiry: Optional[str] = Field(None, description="Fecha de vencimiento")
    blood_type: Optional[str] = Field(None, description="Tipo de sangre")


class VehicleLightData(BaseModel):
    """Datos de vehículo ligero (carros, motos)"""

    plate_number: str = Field(..., description="Número de placa")
    brand: str = Field(..., description="Marca del vehículo")
    model: str = Field(..., description="Modelo del vehículo")
    year: int = Field(..., description="Año del vehículo")
    color: str = Field(..., description="Color del vehículo")
    circulation_card_url: str = Field(..., description="Carnet de circulación")
    rcv_url: str = Field(..., description="Póliza RCV")
    rcv_expiry: Optional[str] = Field(None, description="Vencimiento del RCV")
    vehicle_photo_front_url: str = Field(..., description="Foto frontal del vehículo")
    vehicle_photo_side_url: Optional[str] = Field(None, description="Foto lateral")
    vehicle_photo_back_url: Optional[str] = Field(None, description="Foto trasera")


class VehicleHeavyData(BaseModel):
    """Datos de vehículo pesado (camiones, buses)"""

    plate_number: str = Field(..., description="Número de placa")
    brand: str = Field(..., description="Marca del vehículo")
    model: str = Field(..., description="Modelo del vehículo")
    year: int = Field(..., description="Año del vehículo")
    vehicle_type: str = Field(..., description="Tipo: camion_350, buseta, etc.")
    circulation_card_url: str = Field(..., description="Carnet de circulación")
    rcv_heavy_url: str = Field(..., description="RCV para vehículos pesados")
    rcv_expiry: Optional[str] = Field(None, description="Vencimiento del RCV")

    # Especificaciones de capacidad
    capacity_kg: Optional[int] = Field(None, description="Capacidad en kilos (carga)")
    capacity_liters: Optional[int] = Field(
        None, description="Capacidad en litros (cisterna)"
    )
    capacity_passengers: Optional[int] = Field(
        None, description="Capacidad de pasajeros (bus)"
    )

    vehicle_photo_front_url: str = Field(..., description="Foto frontal")
    vehicle_photo_side_url: Optional[str] = Field(None, description="Foto lateral")
    vehicle_photo_cargo_url: Optional[str] = Field(
        None, description="Foto del área de carga"
    )


class CompanyData(BaseModel):
    """Datos corporativos B2B (Terminales, Líneas)"""

    company_name: str = Field(..., description="Nombre de la empresa/línea")
    rif_type: Literal["J", "G", "V", "E"] = Field(..., description="Tipo de RIF")
    rif_number: str = Field(..., description="Número de RIF (J-12345678-9)")
    rif_url: str = Field(..., description="Foto del RIF")
    registro_mercantil_url: str = Field(..., description="Registro Mercantil")
    acta_constitutiva_url: Optional[str] = Field(None, description="Acta Constitutiva")
    permiso_ruta_url: Optional[str] = Field(
        None, description="Permiso de Ruta (si aplica)"
    )
    office_address: str = Field(..., description="Dirección de la oficina")
    legal_representative: str = Field(..., description="Representante legal")
    legal_representative_cedula: str = Field(
        ..., description="Cédula del representante"
    )


class StoreData(BaseModel):
    """Datos de comercio"""

    store_name: str = Field(..., description="Nombre del comercio")
    store_category: str = Field(
        ..., description="Categoría: restaurante, farmacia, etc."
    )
    rif_type: Literal["J", "V", "E"] = Field(..., description="Tipo de RIF")
    rif_number: str = Field(..., description="Número de RIF")
    rif_url: str = Field(..., description="Foto del RIF")
    store_address: str = Field(..., description="Dirección del local")
    store_photo_exterior_url: str = Field(..., description="Foto exterior del local")
    store_photo_interior_url: Optional[str] = Field(None, description="Foto interior")
    health_permit_url: Optional[str] = Field(
        None, description="Permiso sanitario (si aplica)"
    )


class RentOwnerData(BaseModel):
    """Datos de propietario de vehículo para alquiler"""

    title_property_url: str = Field(..., description="Título de propiedad del vehículo")
    vehicle_plate: str = Field(..., description="Placa del vehículo")
    vehicle_brand: str
    vehicle_model: str
    vehicle_year: int
    vehicle_color: str
    rcv_url: str = Field(..., description="Póliza RCV vigente")
    rcv_expiry: str = Field(..., description="Fecha vencimiento RCV")

    # Fotos detalladas del vehículo
    photo_exterior_front_url: str = Field(..., description="Foto exterior frontal")
    photo_exterior_back_url: str = Field(..., description="Foto exterior trasera")
    photo_exterior_left_url: str = Field(..., description="Foto lateral izquierdo")
    photo_exterior_right_url: str = Field(..., description="Foto lateral derecho")
    photo_interior_dashboard_url: str = Field(..., description="Foto del tablero")
    photo_interior_seats_url: str = Field(..., description="Foto de asientos")
    photo_interior_trunk_url: Optional[str] = Field(
        None, description="Foto del maletero"
    )

    condition_notes: Optional[str] = Field(
        None, description="Notas sobre el estado del vehículo"
    )


# ==================== MODELO PRINCIPAL DE SOLICITUD KYC ====================


class KYCRequest(BaseModel):
    """
    Modelo polimórfico para solicitudes KYC.
    Contiene sub-esquemas opcionales según el tipo de socio.
    """

    kyc_id: str = Field(..., description="ID único de la solicitud")
    user_id: str = Field(..., description="ID del usuario solicitante")
    user_email: str = Field(..., description="Email del usuario")
    user_name: str = Field(..., description="Nombre del usuario")
    user_phone: Optional[str] = Field(None, description="Teléfono del usuario")

    # Tipo de socio que solicita
    requested_role: str = Field(
        ..., description="Rol solicitado: socio_conductor, carga_pesada, etc."
    )
    sub_role: Optional[str] = Field(
        None, description="Sub-rol: mototaxi, camion_750, etc."
    )

    # Estado de la solicitud
    status: KYCStatus = Field(default=KYCStatus.PENDING)
    rejection_reason: Optional[str] = Field(
        None, description="Razón de rechazo si aplica"
    )

    # ==================== SUB-ESQUEMAS OPCIONALES (POLIMÓRFICOS) ====================

    # Datos personales (siempre requeridos)
    personal_data: Optional[PersonalData] = None

    # Datos de licencia (conductores)
    driver_license: Optional[DriverLicenseData] = None

    # Certificado médico (obligatorio para 5ta)
    medical_data: Optional[MedicalData] = None

    # Vehículo ligero (conductor, repartidor)
    vehicle_light: Optional[VehicleLightData] = None

    # Vehículo pesado (carga, chofer interurbano/urbano)
    vehicle_heavy: Optional[VehicleHeavyData] = None

    # Datos corporativos B2B (terminal admin, línea urbana)
    company_data: Optional[CompanyData] = None

    # Datos de comercio
    store_data: Optional[StoreData] = None

    # Datos de rent owner
    rent_owner_data: Optional[RentOwnerData] = None

    # Metadata
    submitted_at: Optional[str] = Field(None, description="Fecha de envío")
    reviewed_at: Optional[str] = Field(None, description="Fecha de revisión")
    reviewed_by: Optional[str] = Field(None, description="Admin que revisó")
    approved_at: Optional[str] = Field(None, description="Fecha de aprobación")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    class Config:
        extra = "allow"  # Permitir campos adicionales para flexibilidad


# ==================== MODELOS DE ENTRADA PARA WIZARD ====================


class KYCWizardConductorRepartidor(BaseModel):
    """Wizard para Conductor (Taxi) / Repartidor (Moto)"""

    # Personal
    cedula_number: str
    cedula_front_url: str
    cedula_back_url: Optional[str] = None

    # Licencia (2da o 3ra)
    license_url: str
    license_number: str
    license_grade: Literal["2da", "3ra"]

    # Vehículo ligero
    plate_number: str
    brand: str
    model: str
    year: int
    color: str
    circulation_card_url: str
    rcv_url: str
    vehicle_photo_front_url: str
    vehicle_photo_side_url: Optional[str] = None


class KYCWizardCargaPesada(BaseModel):
    """Wizard para Carga Pesada / Chofer Interurbano / Chofer Urbano"""

    # Personal
    cedula_number: str
    cedula_front_url: str
    cedula_back_url: Optional[str] = None

    # Licencia 5ta (OBLIGATORIA)
    license_url: str
    license_number: str
    license_grade: Literal["5ta"] = "5ta"

    # Certificado Médico Vial (OBLIGATORIO)
    medical_certificate_url: str
    medical_expiry: Optional[str] = None

    # Vehículo pesado
    plate_number: str
    brand: str
    model: str
    year: int
    vehicle_type: str  # camion_350, buseta, etc.
    circulation_card_url: str
    rcv_heavy_url: str

    # Capacidad
    capacity_kg: Optional[int] = None
    capacity_liters: Optional[int] = None
    capacity_passengers: Optional[int] = None

    vehicle_photo_front_url: str
    vehicle_photo_cargo_url: Optional[str] = None


class KYCWizardB2B(BaseModel):
    """Wizard para Terminal Admin / Línea Urbana (B2B Corporativo)"""

    # Representante Legal
    cedula_number: str
    cedula_front_url: str

    # Datos Corporativos
    company_name: str
    rif_type: Literal["J", "G"]
    rif_number: str
    rif_url: str
    registro_mercantil_url: str
    acta_constitutiva_url: Optional[str] = None
    permiso_ruta_url: Optional[str] = None
    office_address: str
    legal_representative: str


class KYCWizardComercial(BaseModel):
    """Wizard para Socio Comercial"""

    # Personal
    cedula_number: str
    cedula_front_url: str

    # Comercio
    store_name: str
    store_category: str
    rif_type: Literal["J", "V"]
    rif_number: str
    rif_url: str
    store_address: str
    store_photo_exterior_url: str
    store_photo_interior_url: Optional[str] = None
    health_permit_url: Optional[str] = None


class KYCWizardRentOwner(BaseModel):
    """Wizard para Rent Owner"""

    # Personal
    cedula_number: str
    cedula_front_url: str
    cedula_back_url: Optional[str] = None

    # Propiedad del vehículo
    title_property_url: str
    vehicle_plate: str
    vehicle_brand: str
    vehicle_model: str
    vehicle_year: int
    vehicle_color: str

    # RCV
    rcv_url: str
    rcv_expiry: str

    # Fotos detalladas (Exterior)
    photo_exterior_front_url: str
    photo_exterior_back_url: str
    photo_exterior_left_url: str
    photo_exterior_right_url: str

    # Fotos detalladas (Interior)
    photo_interior_dashboard_url: str
    photo_interior_seats_url: str
    photo_interior_trunk_url: Optional[str] = None

    condition_notes: Optional[str] = None


# ==================== HELPERS ====================


def get_required_fields_for_role(role: str) -> dict:
    """Retorna los campos requeridos según el rol"""

    fields = {
        "socio_conductor": {
            "required": ["personal_data", "driver_license", "vehicle_light"],
            "license_grades": ["2da", "3ra"],
            "description": "Conductor de taxi o carro particular",
        },
        "socio_repartidor": {
            "required": ["personal_data", "driver_license", "vehicle_light"],
            "license_grades": ["2da", "3ra"],
            "description": "Repartidor en moto o bicicleta",
        },
        "carga_pesada": {
            "required": [
                "personal_data",
                "driver_license",
                "medical_data",
                "vehicle_heavy",
            ],
            "license_grades": ["5ta"],
            "description": "Operador de carga pesada (camiones, cisternas)",
        },
        "chofer_linea": {
            "required": [
                "personal_data",
                "driver_license",
                "medical_data",
                "vehicle_heavy",
            ],
            "license_grades": ["5ta"],
            "description": "Chofer de línea interurbana",
        },
        "chofer_urbano": {
            "required": [
                "personal_data",
                "driver_license",
                "medical_data",
                "vehicle_heavy",
            ],
            "license_grades": ["5ta"],
            "description": "Chofer de buseta urbana",
        },
        "line_admin": {
            "required": ["personal_data", "company_data"],
            "license_grades": None,
            "description": "Administrador de Terminal/Línea Interurbana (B2B)",
        },
        "urban_line_admin": {
            "required": ["personal_data", "company_data"],
            "license_grades": None,
            "description": "Administrador de Línea Urbana (B2B)",
        },
        "socio_comercial": {
            "required": ["personal_data", "store_data"],
            "license_grades": None,
            "description": "Propietario de comercio",
        },
        "rent_owner": {
            "required": ["personal_data", "rent_owner_data"],
            "license_grades": None,
            "description": "Propietario de vehículo para alquiler",
        },
    }

    return fields.get(role, {"required": ["personal_data"], "license_grades": None})


class LineaTransporteCreate(BaseModel):
    """Registro de una nueva Línea de Transporte"""

    nombre_linea: str  # Ej: "Expresos Occidente"
    rif: str  # RIF de la empresa
    direccion_oficina: str
    telefono_contacto: str
    email_contacto: str
    tipo_servicio: LineServiceType  # interurbano o urbano
    descripcion: Optional[str] = None
    logo_url: Optional[str] = None


class LineaTransporte(BaseModel):
    """Entidad principal: Línea de Transporte / Terminal"""

    linea_id: str
    admin_user_id: str  # Usuario line_admin que administra
    nombre_linea: str
    rif: str
    direccion_oficina: str
    telefono_contacto: str
    email_contacto: str
    tipo_servicio: LineServiceType
    descripcion: Optional[str] = None
    logo_url: Optional[str] = None

    # Billetera centralizada de la Línea
    wallet_balance: float = 0.0
    wallet_held: float = 0.0

    # Estado y KYC
    status: LineStatus = LineStatus.PENDING_KYC
    activation_fee_paid: bool = False

    # Estadísticas
    total_viajes: int = 0
    total_pasajeros: int = 0
    total_earnings: float = 0.0
    avg_rating: float = 5.0

    # Timestamps
    approved_at: Optional[str] = None
    created_at: str


# ==================== VEHÍCULOS DE LA LÍNEA ====================


class VehiculoLineaCreate(BaseModel):
    """Registrar un vehículo en la flota de la Línea"""

    placa: str
    marca: str
    modelo: str
    year: int
    capacidad_pasajeros: int  # Número de asientos
    tipo_vehiculo: str  # buseta, van, expreso, etc.
    foto_url: Optional[str] = None
    circulation_card_url: Optional[str] = None
    rcv_insurance_url: Optional[str] = None


class VehiculoLinea(BaseModel):
    """Vehículo registrado en la flota de una Línea"""

    vehiculo_id: str
    linea_id: str  # FK a LineaTransporte
    placa: str
    marca: str
    modelo: str
    year: int
    capacidad_pasajeros: int
    tipo_vehiculo: str
    foto_url: Optional[str] = None

    # Documentos
    circulation_card_url: Optional[str] = None
    rcv_insurance_url: Optional[str] = None

    # Estado
    status: VehicleStatus = VehicleStatus.ACTIVE

    # Para Rutas Urbanas: código QR único del vehículo
    qr_code: Optional[str] = None
    ruta_asignada_id: Optional[str] = None

    created_at: str


# ==================== CHOFERES DE LA LÍNEA ====================


class ChoferLineaCreate(BaseModel):
    """Registrar un chofer afiliado a la Línea - Mismos requisitos que conductor de taxi"""

    # Datos personales
    nombre: str
    cedula: str
    telefono: str
    email: Optional[str] = None

    # Documentos obligatorios (igual que conductor de taxi)
    cedula_url: str  # Foto de la cédula
    licencia_url: str  # Foto de la licencia
    licencia_categoria: str = "5ta"  # DEBE ser 5ta grado para choferes de línea
    medical_card_url: str  # Certificado médico
    medical_card_expiry: Optional[str] = None  # Fecha vencimiento
    foto_url: Optional[str] = None  # Foto del chofer

    # Antecedentes (opcional pero recomendado)
    antecedentes_url: Optional[str] = None


class ChoferLinea(BaseModel):
    """Chofer afiliado a una Línea de Transporte"""

    chofer_id: str
    linea_id: str  # FK a LineaTransporte
    user_id: Optional[str] = None  # Si tiene cuenta en Xuve (rol chofer_linea)

    nombre: str
    cedula: str
    telefono: str
    email: Optional[str] = None

    # Documentos
    licencia_url: str
    licencia_categoria: str
    foto_url: Optional[str] = None
    medical_card_url: Optional[str] = None

    # Estado
    status: ChoferStatus = ChoferStatus.ACTIVE

    # Estadísticas del chofer
    total_viajes: int = 0
    avg_rating: float = 5.0

    created_at: str


# ==================== VIAJES INTERURBANOS (TERMINAL DIGITAL) ====================


class ViajeInterurbanoCreate(BaseModel):
    """Crear un viaje programado en el Terminal Digital"""

    origen: str
    destino: str
    fecha_salida: str  # ISO format: 2026-03-15T08:00:00
    precio_asiento: float
    capacidad_puestos: int  # Cantidad de puestos para este viaje (manual)
    vehiculo_id: str  # Vehículo asignado
    chofer_id: Optional[str] = None  # Chofer asignado (puede asignarse después)
    descripcion: Optional[str] = None
    punto_encuentro: Optional[str] = None


class ViajeInterurbano(BaseModel):
    """Viaje programado por una Línea de Transporte"""

    viaje_id: str
    linea_id: str  # FK a LineaTransporte
    linea_nombre: str

    # Ruta
    origen: str
    destino: str
    fecha_salida: str

    # Pricing
    precio_asiento: float

    # Vehículo y Chofer asignados
    vehiculo_id: str
    vehiculo_info: Optional[dict] = None  # Marca, modelo, placa
    chofer_id: Optional[str] = None
    chofer_info: Optional[dict] = None  # Nombre, teléfono

    # Capacidad (se obtiene del vehículo)
    capacidad_total: int
    puestos_disponibles: int
    puestos_vendidos: int = 0

    # Financiero
    ingreso_potencial: float
    comision_esperada: float  # 10% del ingreso potencial
    ingresos_reales: Optional[float] = None
    comision_cobrada: Optional[float] = None

    # Detalles
    descripcion: Optional[str] = None
    punto_encuentro: Optional[str] = None

    # Estado: programado, en_curso, completado, cancelado
    status: str = "programado"

    # Reservas embebidas
    reservas: List[dict] = []

    # Timestamps
    iniciado_at: Optional[str] = None
    completado_at: Optional[str] = None
    created_at: str


# ==================== RUTAS URBANAS (MICROPAGOS QR) ====================


class RutaUrbanaCreate(BaseModel):
    """Crear una ruta urbana fija"""

    nombre_ruta: str  # Ej: "Ruta Centro", "Ruta Universidad"
    codigo_ruta: str  # Código corto: "R01", "R02"
    precio_pasaje: float  # Precio fijo del pasaje
    recorrido: Optional[str] = None  # Descripción del recorrido
    horario_inicio: str  # "05:00"
    horario_fin: str  # "22:00"


class RutaUrbana(BaseModel):
    """Ruta urbana fija con micropagos QR"""

    ruta_id: str
    linea_id: str  # FK a LineaTransporte
    nombre_ruta: str
    codigo_ruta: str
    precio_pasaje: float
    recorrido: Optional[str] = None
    horario_inicio: str
    horario_fin: str

    # Vehículos asignados a esta ruta
    vehiculos_asignados: List[str] = []  # Lista de vehiculo_ids

    # QR maestro de la ruta (opcional)
    qr_code_ruta: Optional[str] = None

    # Estadísticas
    total_pasajes_hoy: int = 0
    total_ingresos_hoy: float = 0.0

    status: str = "active"
    created_at: str


# ==================== RESERVAS / BOLETOS ====================


class ReservaInterurbano(BaseModel):
    """Reserva de boleto para viaje interurbano"""

    reserva_id: str
    viaje_id: str
    user_id: str  # Cliente que reservó

    # Datos del pasajero
    nombre_pasajero: str
    telefono_pasajero: Optional[str] = None
    cedula_pasajero: Optional[str] = None

    # Detalles de la reserva
    cantidad_puestos: int
    precio_unitario: float
    total: float

    # Info de la Línea y Chofer (para el boleto)
    linea_nombre: str
    chofer_nombre: Optional[str] = None
    chofer_telefono: Optional[str] = None
    vehiculo_placa: Optional[str] = None

    # Info del viaje
    origen: str
    destino: str
    fecha_salida: str
    punto_encuentro: Optional[str] = None

    # Estado: confirmada, cancelada, abordada, no_show
    status: str = "confirmada"

    # Timestamps
    cancelada_at: Optional[str] = None
    created_at: str


# ==================== MICROPAGO QR ====================


class MicropagoQR(BaseModel):
    """Registro de un micropago por QR en ruta urbana"""

    pago_id: str
    ruta_id: str
    vehiculo_id: str
    chofer_id: Optional[str] = None
    user_id: str  # Cliente que pagó

    monto: float
    fee_xuve: float  # Fee fijo de Xuve
    monto_linea: float  # Monto que recibe la línea
    metodo_pago: str  # "wallet", "qr_externo"

    created_at: str


# ==================== RUTAS URBANAS EXTENDIDAS ====================


class RutaUrbanaCreateExtended(BaseModel):
    """Crear una ruta urbana con asignaciones"""

    nombre_ruta: str  # Ej: "Ruta 2: Centro - Universidad"
    codigo_ruta: str  # Código corto: "R02"
    tarifa: float  # Tarifa fija del pasaje (Ej: $0.50)
    descripcion: Optional[str] = None  # Descripción del recorrido
    horario_inicio: str = "05:00"  # Hora inicio operaciones
    horario_fin: str = "22:00"  # Hora fin operaciones
    color: Optional[str] = "#8B5CF6"  # Color para identificar en mapa


class AsignacionRuta(BaseModel):
    """Asignar un chofer y vehículo a una ruta"""

    ruta_id: str
    chofer_id: str
    vehiculo_id: str


# ==================== GEOLOCALIZACIÓN EN TIEMPO REAL ====================


class GeoUpdate(BaseModel):
    """Actualización de ubicación del chofer"""

    lat: float
    lng: float
    heading: Optional[float] = None  # Dirección en grados
    speed: Optional[float] = None  # Velocidad km/h


class RecorridoActivo(BaseModel):
    """Recorrido activo de un chofer en ruta urbana"""

    recorrido_id: str
    ruta_id: str
    chofer_id: str
    vehiculo_id: str
    linea_id: str

    # Info para mostrar
    ruta_nombre: str
    vehiculo_placa: str
    chofer_nombre: str
    tarifa: float

    # Geolocalización actual
    lat: float
    lng: float
    heading: Optional[float] = None
    speed: Optional[float] = None

    # QR data (para generar código)
    qr_data: str  # JSON string con info del pago

    # Estado
    pasajeros_hoy: int = 0
    ingresos_hoy: float = 0.0

    iniciado_at: str
    ultima_actualizacion: str


class UrbanLineCreate(BaseModel):
    """Registro de una nueva Línea de Transporte Urbano"""

    nombre_linea: str  # Ej: "Transporte San Benito"
    rif: str  # RIF de la empresa
    direccion_oficina: str
    telefono_contacto: str
    email_contacto: str
    zona_operacion: str  # Ej: "Mérida Centro", "Barquisimeto Sur"
    descripcion: Optional[str] = None
    logo_url: Optional[str] = None


class UrbanVehiculoCreate(BaseModel):
    """Registrar un vehículo (buseta/van) en la flota urbana"""

    placa: str
    marca: str
    modelo: str
    year: int
    capacidad_pasajeros: int  # Número de asientos
    tipo_vehiculo: str = "buseta"  # buseta, van, minibus
    foto_url: Optional[str] = None
    circulation_card_url: Optional[str] = None
    rcv_insurance_url: Optional[str] = None


class UrbanChoferCreate(BaseModel):
    """Registrar un chofer de línea urbana"""

    # Datos personales
    nombre: str
    cedula: str
    telefono: str
    email: Optional[str] = None

    # Documentos obligatorios
    cedula_url: str
    licencia_url: str
    licencia_categoria: str = "5ta"  # DEBE ser 5ta grado
    medical_card_url: str
    medical_card_expiry: Optional[str] = None
    foto_url: Optional[str] = None
    antecedentes_url: Optional[str] = None


class UrbanRutaCreate(BaseModel):
    """Crear una ruta urbana con trazado en mapa"""

    nombre_ruta: str  # Ej: "Ruta 2: Centro - Universidad"
    codigo_ruta: str  # Código corto: "R02"
    tarifa: float  # Tarifa fija del pasaje
    descripcion: Optional[str] = None
    horario_inicio: str = "05:00"
    horario_fin: str = "22:00"
    color: str = "#10B981"  # Color para el mapa

    # Trazado de la ruta (lista de puntos para polyline)
    waypoints: Optional[List[dict]] = None  # [{lat, lng, nombre_parada}]


class UrbanAsignacionCreate(BaseModel):
    """Asignar chofer y vehículo a una ruta"""

    ruta_id: str
    chofer_id: str
    vehiculo_id: str


class UrbanGeoUpdate(BaseModel):
    """Actualización de ubicación del chofer urbano"""

    lat: float
    lng: float
    heading: Optional[float] = None
    speed: Optional[float] = None


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

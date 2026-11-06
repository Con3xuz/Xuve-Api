"""
KYC Models - Sistema de Verificación Modular para OMNI SuperApp

Este módulo define los esquemas polimórficos de KYC para cada tipo de socio:
- Conductor / Repartidor: Vehículos ligeros
- Carga Pesada / Chofer Interurbano / Chofer Urbano: Vehículos pesados (5ta)
- Terminal Admin / Línea Urbana: Corporativo B2B
- Comercial: Tiendas y comercios
- Rent Owner: Propietarios de vehículos para alquiler
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum

# ==================== ENUMS Y CONSTANTES ====================


class KYCStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    INCOMPLETE = "incomplete"


class LicenseGrade(str, Enum):
    SEGUNDA = "2da"
    TERCERA = "3ra"
    CUARTA = "4ta"
    QUINTA = "5ta"


# Roles que pueden solicitar KYC
KYC_ROLE_TYPES = [
    "socio_conductor",  # Taxi/Carro particular
    "socio_repartidor",  # Moto delivery / Bicicleta
    "carga_pesada",  # Camionero
    "chofer_linea",  # Chofer interurbano
    "chofer_urbano",  # Chofer de buseta urbana
    "line_admin",  # Admin Terminal B2B
    "urban_line_admin",  # Admin Línea Urbana B2B
    "socio_comercial",  # Comerciante
    "rent_owner",  # Propietario Rent-a-Car
]

# Categorías de vehículos
VEHICLE_CATEGORIES = {
    "ligero": [
        "carro_particular",
        "taxi_linea",
        "mototaxi",
        "moto_delivery",
        "bicicleta",
    ],
    "pesado": [
        "camion_350",
        "camion_750",
        "camion_cava",
        "cisterna",
        "buseta",
        "van",
        "expreso",
        "autobus",
    ],
}


# ==================== SUB-ESQUEMAS OPCIONALES ====================


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

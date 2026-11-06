"""
Modelos para el Sistema de Líneas de Transporte Urbano

Este módulo implementa las entidades para las líneas de transporte público urbano
(busetas, rutas fijas), separado del modelo de terminales interurbanos.

Entidades:
- LineaUrbana: Línea de transporte urbano (administrada por urban_line_admin)
- RutaUrbanaV2: Rutas con trazado en mapa
- AsignacionChoferUrbano: Asignación de chofer a unidad y ruta
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UrbanLineStatus(str, Enum):
    PENDING_KYC = "pending_kyc"
    APPROVED = "approved"
    SUSPENDED = "suspended"


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

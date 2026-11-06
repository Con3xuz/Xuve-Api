"""
Modelos para el Sistema B2B de Líneas de Transporte

Jerarquía:
- LineaTransporte (Terminal): Entidad principal con billetera centralizada
  - VehiculoLinea: Flota de vehículos registrados por la Línea
  - ChoferLinea: Choferes afiliados a la Línea
  - ViajeInterurbano: Viajes programados (Terminal Digital)
  - RutaUrbana: Rutas fijas con micropagos (Torniquete QR)
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class LineServiceType(str, Enum):
    INTERURBANO = "interurbano"  # Terminal Digital - Viajes programados
    URBANO = "urbano"  # Rutas Fijas - Micropagos QR


class LineStatus(str, Enum):
    PENDING_KYC = "pending_kyc"
    APPROVED = "approved"
    SUSPENDED = "suspended"


class VehicleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class ChoferStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


# ==================== LÍNEA DE TRANSPORTE (TERMINAL) ====================


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

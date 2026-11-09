"""
Módulo de Modelos SQL (PostgreSQL - Esquema `xuve`).
Expone los Modelos de Base de Datos con consultas SQL directas y el motor `db`.
"""

from models.base import PostgresBaseModel, Database, Collection, db
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
    UserModel,
    UserSessionModel,
    EmailVerificationModel,
    PasswordResetModel,
    SocioConductorModel,
    SocioRepartidorModel,
    SocioComercialModel,
    SocioCargaPesadaModel,
    SocioInterurbanoModel,
    PlatformConfigModel,
    DailySubscriptionModel,
    SubscriptionHistoryModel,
    SubscriptionPaymentModel,
    User,
)
from models.wallet_models import (
    TransactionType,
    WalletModel,
    WalletHoldModel,
    TransactionModel,
    ExchangeRateModel,
    Transaction,
    ExchangeRate,
)
from models.service_models import (
    ServiceType,
    ServiceStatus,
    ServiceModel,
    RatingModel,
    ProviderAvailabilityModel,
    ServiceMessageModel,
    Service,
)
from models.market_models import (
    MarketStoreModel,
    MarketProductModel,
    MarketOrderModel,
    OrderModel,
    MarketStore,
    MarketProduct,
    Order,
)
from models.market_category_models import (
    StoreProfileModel,
    StoreProfile,
)
from models.product_models import (
    ProductStatus,
    ProductModel,
)
from models.driver_models import DriverModel, Driver
from models.kyc_models import (
    KYCStatus,
    LicenseGrade,
    KYC_ROLE_TYPES,
    VEHICLE_CATEGORIES,
    KYCRequestModel,
    KYCRequest,
)
from models.line_models import (
    LineServiceType,
    LineStatus,
    VehicleStatus,
    ChoferStatus,
    LineaTransporteModel,
    VehiculoLineaModel,
    ChoferLineaModel,
    ViajeInterurbanoModel,
    ReservaInterurbanoModel,
    ViajeModel,
    RutaUrbanaModel,
    RutaUrbanaV2Model,
    RecorridoActivoModel,
    RecorridoHistoricoModel,
    AsignacionRutaModel,
    MicropagoUrbanoModel,
    MicropagoQRModel,
    RutaModel,
    CotizacionCargaModel,
    VehiculoCargaModel,
    ServicioCargaModel,
    OperadorCargaModel,
    NotificacionCargaModel,
)
from models.urban_line_models import (
    UrbanLineStatus,
    LineaUrbanaModel,
    VehiculoUrbanoModel,
    ChoferUrbanoModel,
    RecorridoUrbanoModel,
    RecorridoUrbanoHistoricoModel,
    AsignacionUrbanaModel,
)
from models.rent_models import (
    RentCarModel,
    RentRequestModel,
    RentOwnerModel,
    RentVehicleModel,
    RentalModel,
)
from models.chat_models import (
    ChatConversationModel,
    ChatMessageModel,
    NotificationModel,
    FixedRouteModel,
    ChatMessage,
    FixedRoute,
)
from models.prescription_models import MedicoModel, PrescriptionModel
from models.payment_method_models import (
    PAYMENT_METHOD_TYPES,
    PAYMENT_METHOD_ACTIVE,
    PAYMENT_METHOD_PENDING,
    ACCOUNT_SUSPENDED_PENDING_REVIEW,
    PaymentMethodModel,
)

from models.catalog_models import (
    BusinessCategoryModel,
    ProductCategoryModel,
    PlatformSettingModel,
    CargoRateModel,
)

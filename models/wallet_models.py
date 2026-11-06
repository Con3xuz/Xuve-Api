from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum


class TransactionType(str, Enum):
    """Tipos de transacción en la billetera"""

    RECHARGE = "RECHARGE"  # Recarga de saldo
    WITHDRAW = "WITHDRAW"  # Retiro de saldo
    ACTIVATION_FEE = "ACTIVATION_FEE"  # Fee de activación ($1.00)
    COMMISSION_DEDUCTION = "COMMISSION_DEDUCTION"  # Comisión por viaje (10%)
    SERVICE_PAYMENT = "SERVICE_PAYMENT"  # Pago por servicio
    TOLL = "TOLL"  # Peaje diario
    HOLD = "HOLD"  # Fondos congelados
    HOLD_RELEASE = "HOLD_RELEASE"  # Liberación de hold
    HOLD_CHARGE = "HOLD_CHARGE"  # Cobro de hold


# Constantes del modelo financiero
ACTIVATION_FEE_AMOUNT = 1.00  # Fee de activación en USD
MIN_BALANCE_TO_ACTIVATE = 5.00  # Saldo mínimo para cobrar fee
MIN_BALANCE_TO_CONNECT = 1.00  # Saldo mínimo para conectarse
COMMISSION_RATE = 0.10  # 10% de comisión por viaje (conductores)
MARKET_COMMISSION_RATE = 0.12  # 12% de comisión market (comercios)
HEAVY_TRANSPORT_COMMISSION = 0.10  # 10% de comisión carga pesada
MIN_BALANCE_HEAVY_TRANSPORT = 10.00  # Saldo mínimo recomendado para carga pesada


class WalletRecharge(BaseModel):
    amount_bs: float
    payment_method: str  # pago_movil, binance_pay
    reference: str


class WalletWithdraw(BaseModel):
    amount_usd: float
    bank_name: str
    phone: str
    cedula: str


class WalletHold(BaseModel):
    amount_usd: float
    reason: str  # rent_deposit, service_guarantee
    reference_id: str


class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    transaction_id: str
    user_id: str
    amount_usd: float
    type: str  # Usar TransactionType enum values
    status: str  # pending, completed, failed
    reference: Optional[str] = None
    description: str
    created_at: datetime


class ExchangeRate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rate_id: str
    usd_to_bs: float
    updated_at: datetime
    updated_by: str

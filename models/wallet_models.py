"""
Modelos SQL de Billetera, Retenciones (Holds), Transacciones y Tasas de Cambio (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from enum import Enum
from models.base import PostgresBaseModel


class TransactionType(str, Enum):
    """Tipos de transacción financiera en la billetera."""
    RECHARGE = "RECHARGE"
    WITHDRAW = "WITHDRAW"
    ACTIVATION_FEE = "ACTIVATION_FEE"
    COMMISSION_DEDUCTION = "COMMISSION_DEDUCTION"
    SERVICE_PAYMENT = "SERVICE_PAYMENT"
    TOLL = "TOLL"
    HOLD = "HOLD"
    HOLD_RELEASE = "HOLD_RELEASE"
    HOLD_CHARGE = "HOLD_CHARGE"


# Constantes financieras de dominio


class WalletModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.wallets`."""
    _table_name = "wallets"

    @classmethod
    async def find_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.wallets WHERE doc->>'user_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, user_id)


class WalletHoldModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.wallet_holds`."""
    _table_name = "wallet_holds"

    @classmethod
    async def find_by_hold_id(cls, hold_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.wallet_holds WHERE doc->>'hold_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, hold_id)

    @classmethod
    async def list_by_user_id(cls, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.wallet_holds WHERE doc->>'user_id' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, user_id, limit)


class TransactionModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.transactions`."""
    _table_name = "transactions"

    @classmethod
    async def find_by_id(cls, transaction_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.transactions WHERE doc->>'transaction_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, transaction_id)

    @classmethod
    async def list_by_user_id(cls, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.transactions WHERE doc->>'user_id' = $1 ORDER BY created_at DESC LIMIT $2"
        return await cls.sql_fetch_all(sql, user_id, limit)


class ExchangeRateModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.exchange_rates`."""
    _table_name = "exchange_rates"

    @classmethod
    async def get_latest(cls) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.exchange_rates ORDER BY created_at DESC LIMIT 1"
        return await cls.sql_fetch_one(sql)


Transaction = TransactionModel
ExchangeRate = ExchangeRateModel

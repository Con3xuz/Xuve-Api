"""
Modelos SQL de Métodos de Pago del Usuario (PostgreSQL - Esquema `xuve`).
"""

from typing import Any, Dict, List, Optional
from models.base import PostgresBaseModel

PAYMENT_METHOD_TYPES = ["PAGO_MOVIL", "BANK_ACCOUNT_VE", "ZELLE", "BINANCE_PAY"]
PAYMENT_METHOD_ACTIVE = "ACTIVE"
PAYMENT_METHOD_PENDING = "PENDING_VALIDATION"
ACCOUNT_SUSPENDED_PENDING_REVIEW = "SUSPENDED_PENDING_REVIEW"


def mask_identifier(value: Optional[str], visible: int = 4) -> Optional[str]:
    """Enmascara un identificador sensible dejando visibles los últimos dígitos."""
    if not value:
        return None
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


class PaymentMethodModel(PostgresBaseModel):
    """Modelo SQL para la tabla `xuve.payment_methods`."""
    _table_name = "payment_methods"

    @classmethod
    async def find_by_id(cls, method_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.payment_methods WHERE doc->>'method_id' = $1 LIMIT 1"
        return await cls.sql_fetch_one(sql, method_id)

    @classmethod
    async def list_by_user_id(cls, user_id: str) -> List[Dict[str, Any]]:
        sql = "SELECT doc FROM xuve.payment_methods WHERE doc->>'user_id' = $1 ORDER BY created_at DESC"
        return await cls.sql_fetch_all(sql, user_id)

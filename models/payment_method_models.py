"""
Modelos de métodos de pago del usuario (KYC progresivo — T&C cláusulas 3.2 y 6).

El backend NO valida el formato de los instrumentos: la única fuente de verdad
es xuve-kyc-service (pre-validación sintáctica y motor de titularidad). Aquí
solo se acota la forma del payload que viaja al microservicio y los estados con
los que se persiste el instrumento.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

# Tipos soportados por el motor de titularidad del microservicio.
PAYMENT_METHOD_TYPES = ["PAGO_MOVIL", "BANK_ACCOUNT_VE", "ZELLE", "BINANCE_PAY"]

# Estados del instrumento en la BD del backend principal:
# ACTIVE              -> titularidad confirmada (MATCH), utilizable.
# PENDING_VALIDATION  -> en revisión manual (MANUAL_REVIEW), no utilizable aún.
PAYMENT_METHOD_ACTIVE = "ACTIVE"
PAYMENT_METHOD_PENDING = "PENDING_VALIDATION"

# Estado de cuenta al acumular 3 strikes de titularidad (cláusula 6).
ACCOUNT_SUSPENDED_PENDING_REVIEW = "SUSPENDED_PENDING_REVIEW"


class PaymentMethodPayload(BaseModel):
    """Espejo del borrador que entiende el microservicio.

    Los campos que no apliquen al `method_type` se ignoran allá, por lo que la
    app puede mandar el estado completo del formulario. `extra="forbid"` evita
    que campos desconocidos viajen silenciosamente al servicio estricto.
    """

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
        """Payload para el microservicio: solo los campos presentes."""
        return self.model_dump(exclude_none=True)


def mask_identifier(value: Optional[str], visible: int = 4) -> Optional[str]:
    """Enmascara un identificador sensible dejando visibles los últimos dígitos.

    El instrumento nunca se persiste en claro (para deduplicar cuentas se usa el
    instrument_fingerprint SHA-256 que devuelve el microservicio).
    """
    if not value:
        return None
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]

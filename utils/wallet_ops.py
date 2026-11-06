"""
Operaciones atómicas de billetera (anti-TOCTOU).
================================================
Las verificaciones de saldo se hacen DENTRO del mismo UPDATE en PostgreSQL, no
en Python, para evitar condiciones de carrera (dos peticiones concurrentes que
ambas pasan el chequeo y dejan el saldo negativo / doble gasto).

Operan directamente sobre la tabla `omni.users` (columna JSONB `doc`) usando el
pool de asyncpg. El "disponible" es siempre `wallet_balance - wallet_held`.
"""

from db.pg import get_pool

_USERS = "omni.users"

# Expresiones JSONB reutilizables sobre la fila `doc`.
_BAL = "COALESCE((doc ->> 'wallet_balance')::numeric, 0)"
_HELD = "COALESCE((doc ->> 'wallet_held')::numeric, 0)"


class InsufficientFunds(Exception):
    """Saldo disponible insuficiente para la operación solicitada."""


async def debit_available_atomic(user_id: str, amount: float) -> None:
    """Descuenta `amount` de wallet_balance SOLO si el disponible lo cubre.

    Atómico: el WHERE comprueba (balance - held) >= amount en la misma sentencia.
    Lanza InsufficientFunds si ningún registro cumple la condición.
    """
    if amount <= 0:
        raise InsufficientFunds("El monto debe ser mayor que cero")
    sql = f"""
        UPDATE {_USERS}
        SET doc = jsonb_set(
            doc, '{{wallet_balance}}', to_jsonb({_BAL} - $2::numeric), true)
        WHERE doc ->> 'user_id' = $1
          AND ({_BAL} - {_HELD}) >= $2::numeric
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        status = await conn.execute(sql, user_id, amount)
    if int(status.split()[-1]) == 0:
        raise InsufficientFunds("Saldo disponible insuficiente")


async def hold_funds_atomic(user_id: str, amount: float) -> None:
    """Incrementa wallet_held en `amount` SOLO si el disponible lo cubre.

    Congela fondos (garantías) de forma atómica, sin tocar wallet_balance.
    Lanza InsufficientFunds si el disponible no alcanza.
    """
    if amount <= 0:
        raise InsufficientFunds("El monto debe ser mayor que cero")
    sql = f"""
        UPDATE {_USERS}
        SET doc = jsonb_set(
            doc, '{{wallet_held}}', to_jsonb({_HELD} + $2::numeric), true)
        WHERE doc ->> 'user_id' = $1
          AND ({_BAL} - {_HELD}) >= $2::numeric
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        status = await conn.execute(sql, user_id, amount)
    if int(status.split()[-1]) == 0:
        raise InsufficientFunds("Saldo disponible insuficiente")


async def credit_balance_atomic(user_id: str, amount: float) -> None:
    """Acredita `amount` a wallet_balance de forma atómica (recargas confirmadas)."""
    if amount <= 0:
        return
    sql = f"""
        UPDATE {_USERS}
        SET doc = jsonb_set(
            doc, '{{wallet_balance}}', to_jsonb({_BAL} + $2::numeric), true)
        WHERE doc ->> 'user_id' = $1
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(sql, user_id, amount)

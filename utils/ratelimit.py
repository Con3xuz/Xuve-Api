"""
Rate limiter compartido (slowapi).
==================================
Una ÚNICA instancia de Limiter para toda la app: la usa el middleware
(`app.state.limiter`) y todos los decoradores `@limiter.limit(...)` por ruta.

- `default_limits` aplica un techo base a TODAS las rutas (mitiga abuso en
  endpoints no decorados). Los límites por ruta siguen siendo más estrictos.
- `RATE_LIMIT_ENABLED` permite desactivarlo en el arnés de tests (que hace
  muchos logins desde una sola IP). En producción queda activo por defecto.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    enabled=RATE_LIMIT_ENABLED,
)

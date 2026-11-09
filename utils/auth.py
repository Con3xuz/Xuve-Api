from fastapi import Request, HTTPException
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
import bcrypt
import jwt
import os

load_dotenv(Path(__file__).parent.parent / ".env")

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable must be set for security.")
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str, role: str, token_version: int = 0) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        # Permite revocar TODOS los JWT de un usuario (p.ej. al cambiar contraseña):
        # se incrementa token_version en el usuario y los tokens viejos dejan de validar.
        "tv": token_version,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    from models.user_models import UserModel, UserSessionModel

    # Check cookie first, then Authorization header
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Check if it's a session token from Google Auth
    session = await UserSessionModel.find_by_token(token)
    if session:
        expires_at = session.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired")

        user = await UserModel.find_by_id(session["user_id"])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        _require_active(user)
        return user

    # Try JWT token
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await UserModel.find_by_id(payload["user_id"])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        # Revocación por versión: el token debe coincidir con el token_version actual.
        if int(payload.get("tv", 0)) != int(user.get("token_version", 0)):
            raise HTTPException(status_code=401, detail="Token revoked")
        _require_active(user)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _require_active(user: dict) -> None:
    """Rechaza cuentas que no estén activas (suspendidas / inactivas)."""
    if user.get("status", "active") != "active":
        raise HTTPException(status_code=403, detail="Cuenta no activa")

"""Controlador de auth - Validaciones y lógica de negocio."""
from models import *
from fastapi import APIRouter, HTTPException, Depends, Response, Request
from datetime import datetime, timezone, timedelta
import os
import uuid
import secrets
import asyncio

import jwt
from jwt import PyJWKClient

from models import db
from utils.auth import hash_password, verify_password, create_token, get_current_user
from utils.email_service import (
    send_welcome_email,
    send_verification_email,
    send_password_reset_email,
)
from controllers.validators import (
    UserCreate,
    UserLogin,
    VerifyEmail,
    ResendVerification,
    ForgotPassword,
    ResetPassword,
    VALID_ROLES,
    PRIVILEGED_ROLES,
    SELF_REGISTRABLE_ROLE,
)

# Rate limiting (instancia compartida)
from utils.ratelimit import limiter



@limiter.limit("5/minute")
async def register(request: Request, user_data: UserCreate):
    existing = await UserModel.find_one({"email": user_data.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # SEGURIDAD: el registro NUNCA asigna un rol de socio/admin directamente.
    # El rol efectivo nace siempre como "user"; si el cliente pide otro rol válido
    # (p.ej. socio_conductor) se guarda como `pending_role` (intención) para que el
    # frontend enrute a KYC. El rol solo se eleva tras aprobación de KYC.
    requested = (user_data.role or SELF_REGISTRABLE_ROLE).strip()
    if requested in PRIVILEGED_ROLES:
        raise HTTPException(
            status_code=403, detail="No puedes registrarte con ese rol"
        )
    pending_role = (
        requested
        if requested != SELF_REGISTRABLE_ROLE and requested in VALID_ROLES
        else None
    )

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    user_doc = {
        "user_id": user_id,
        "email": user_data.email,
        "password": hash_password(user_data.password),
        "name": user_data.name,
        "phone": user_data.phone,
        "role": SELF_REGISTRABLE_ROLE,
        # Ningún usuario nace verificado: el KYC arranca en "pending" y solo lo
        # eleva la aprobación de KYC.
        "kyc_status": "pending",
        "email_verified": False,
        "wallet_balance": 0.0,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if pending_role:
        user_doc["pending_role"] = pending_role
    await UserModel.insert_one(user_doc)

    # Genera y envía el código de verificación de email (best-effort).
    await _issue_verification_code(user_data.email)

    # Correo de bienvenida (best-effort: no debe romper el registro si SMTP falla).
    await send_welcome_email(user_data.email, user_data.name)

    token = create_token(user_id, user_doc["role"])
    del user_doc["password"]
    if "_id" in user_doc:
        del user_doc["_id"]

    return {"user": user_doc, "token": token}


# ---------------------------------------------------------------------------
# Verificación de email (código de 6 dígitos, expira en 15 min)
# ---------------------------------------------------------------------------
VERIFICATION_TTL_MINUTES = 15
RESET_TTL_MINUTES = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expired(iso_ts: str) -> bool:
    """True si el timestamp ISO ya pasó (tolerante a naive/aware)."""
    try:
        exp = datetime.fromisoformat(iso_ts)
    except (TypeError, ValueError):
        return True
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp < _now()


async def _issue_verification_code(email: str) -> str:
    """Crea (o reemplaza) el código de verificación de un email y lo envía."""
    code = f"{secrets.randbelow(10**6):06d}"
    expires_at = (_now() + timedelta(minutes=VERIFICATION_TTL_MINUTES)).isoformat()
    # Un único código vigente por email: borra los anteriores.
    await EmailVerificationModel.delete_many({"email": email})
    await EmailVerificationModel.insert_one(
        {
            "email": email,
            "code": code,
            "expires_at": expires_at,
            "created_at": _now().isoformat(),
        }
    )
    await send_verification_email(email, code)
    return code


@limiter.limit("5/minute")
async def verify_email(request: Request, data: VerifyEmail):
    """Valida el código de verificación y marca el email como verificado."""
    record = await EmailVerificationModel.find_one(
        {"email": data.email, "code": data.code}, {"_id": 0}
    )
    if not record:
        raise HTTPException(status_code=400, detail="Código inválido")
    if _expired(record.get("expires_at", "")):
        await EmailVerificationModel.delete_many({"email": data.email})
        raise HTTPException(status_code=400, detail="Código expirado")

    await UserModel.update_one(
        {"email": data.email}, {"$set": {"email_verified": True}}
    )
    await EmailVerificationModel.delete_many({"email": data.email})
    return {"message": "Email verificado", "email_verified": True}


@limiter.limit("3/minute")
async def resend_verification(request: Request, data: ResendVerification):
    """Reenvía un código de verificación si el usuario existe y no está verificado."""
    user = await UserModel.find_one({"email": data.email}, {"_id": 0})
    # No revelar si el email existe: respuesta uniforme.
    if user and not user.get("email_verified", False):
        await _issue_verification_code(data.email)
    return {"message": "Si el email existe y no está verificado, se envió un código."}


# ---------------------------------------------------------------------------
# Recuperación de contraseña (token urlsafe de un solo uso, expira en 1h)
# ---------------------------------------------------------------------------
@limiter.limit("3/minute")
async def forgot_password(request: Request, data: ForgotPassword):
    """Genera un token de reset y lo envía por correo. No revela si el email existe."""
    user = await UserModel.find_one({"email": data.email}, {"_id": 0})
    if user:
        token = secrets.token_urlsafe(32)
        expires_at = (_now() + timedelta(minutes=RESET_TTL_MINUTES)).isoformat()
        # Invalida tokens anteriores del mismo email.
        await PasswordResetModel.delete_many({"email": data.email})
        await PasswordResetModel.insert_one(
            {
                "email": data.email,
                "token": token,
                "used": False,
                "expires_at": expires_at,
                "created_at": _now().isoformat(),
            }
        )
        base = os.environ.get("FRONTEND_BASE_URL", "https://app.xuve.net").rstrip("/")
        reset_link = f"{base}/reset-password?token={token}"
        await send_password_reset_email(data.email, reset_link)
    return {"message": "Si el email existe, se envió un enlace de recuperación."}


@limiter.limit("5/minute")
async def reset_password(request: Request, data: ResetPassword):
    """Valida el token y actualiza la contraseña. El token es de un solo uso."""
    record = await PasswordResetModel.find_one({"token": data.token}, {"_id": 0})
    if not record or record.get("used", False):
        raise HTTPException(status_code=400, detail="Token inválido o ya utilizado")
    if _expired(record.get("expires_at", "")):
        await PasswordResetModel.delete_many({"token": data.token})
        raise HTTPException(status_code=400, detail="Token expirado")

    email = record["email"]
    user = await UserModel.find_one({"email": email}, {"_id": 0})
    # Cambia el hash e invalida TODOS los JWT existentes (token_version++).
    await UserModel.update_one(
        {"email": email},
        {
            "$set": {"password": hash_password(data.password)},
            "$inc": {"token_version": 1},
        },
    )
    # Token de un solo uso: invalidar inmediatamente.
    await PasswordResetModel.delete_many({"email": email})
    # Cierra sesiones de Google activas para forzar re-login con la nueva contraseña.
    if user:
        await UserSessionModel.delete_many({"user_id": user["user_id"]})
    return {"message": "Contraseña actualizada correctamente"}


@limiter.limit("5/minute")
async def login(request: Request, credentials: UserLogin, response: Response):
    user = await UserModel.find_one({"email": credentials.email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(credentials.password, user.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.get("status", "active") != "active":
        raise HTTPException(status_code=403, detail="Cuenta no activa")

    token = create_token(
        user["user_id"], user["role"], user.get("token_version", 0)
    )

    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )

    user_response = {k: v for k, v in user.items() if k != "password"}
    return {"user": user_response, "token": token}


# ---------------------------------------------------------------------------
# Login con Google — verificación DIRECTA del ID token contra Google (JWKS).
# Reemplaza la validación vía terceros (emergentagent). El cliente obtiene un
# ID token de Google Sign-In y lo envía; aquí se valida la firma con las claves
# públicas de Google, el emisor, la audiencia y la expiración.
# ---------------------------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

# Cliente JWKS (cachea las claves públicas de Google entre peticiones).
_google_jwk_client = PyJWKClient(GOOGLE_JWKS_URL)


def _verify_google_id_token(token: str) -> dict:
    """Verifica firma (RS256 contra JWKS de Google) + audiencia + expiración.
    Lanza jwt.PyJWTError si el token no es válido. Bloqueante -> usar en hilo."""
    signing_key = _google_jwk_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=GOOGLE_OAUTH_CLIENT_ID,
    )


@limiter.limit("10/minute")
async def google_session(request: Request, response: Response):
    """Inicia sesión con Google verificando el ID token directamente contra Google."""
    if not GOOGLE_OAUTH_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Login con Google no configurado (falta GOOGLE_OAUTH_CLIENT_ID).",
        )

    body = await request.json()
    # El cliente envía el ID token de Google (Google Sign-In). Aceptamos ambos nombres.
    id_token = body.get("id_token") or body.get("credential")
    if not id_token:
        raise HTTPException(status_code=400, detail="id_token requerido")

    # Verificación oficial (no bloquea el event loop: corre en un hilo).
    try:
        claims = await asyncio.to_thread(_verify_google_id_token, id_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token de Google inválido")

    # Defensa en profundidad: emisor de Google y email verificado por Google.
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise HTTPException(status_code=401, detail="Emisor de token no válido")
    if not claims.get("email") or not claims.get("email_verified", False):
        raise HTTPException(status_code=401, detail="Email de Google no verificado")

    email = claims["email"]
    google_sub = claims.get("sub")  # identificador estable de Google

    # Busca o crea el usuario.
    user = await UserModel.find_one({"email": email}, {"_id": 0})
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user_doc = {
            "user_id": user_id,
            "email": email,
            "name": claims.get("name", ""),
            "picture": claims.get("picture", ""),
            "phone": "",
            "role": "user",
            "google_sub": google_sub,
            "email_verified": True,
            "wallet_balance": 0.0,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await UserModel.insert_one(user_doc)
        user = await UserModel.find_one({"user_id": user_id}, {"_id": 0})

    # Token de sesión PROPIO (no se confía en ningún token externo).
    session_token = f"session_{uuid.uuid4().hex}"
    await UserSessionModel.insert_one(
        {
            "user_id": user["user_id"],
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )

    return {"user": user, "token": session_token}


async def get_me(user: dict = Depends(get_current_user)):
    return user


async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await UserSessionModel.delete_one({"session_token": token})

    response.delete_cookie("session_token", path="/")
    return {"message": "Logged out"}


async def update_profile(request: Request, user: dict = Depends(get_current_user)):
    """Update user profile (name, phone, picture)"""
    body = await request.json()

    # Only allow updating specific fields
    allowed_fields = ["name", "phone", "picture"]
    update_data = {
        k: v for k, v in body.items() if k in allowed_fields and v is not None
    }

    if not update_data:
        return user

    await UserModel.update_one({"user_id": user["user_id"]}, {"$set": update_data})

    updated_user = await UserModel.find_one(
        {"user_id": user["user_id"]}, {"_id": 0, "password": 0}
    )
    return updated_user

"""
XUVE - Servicio de correo transaccional (SMTP).
================================================
Envío de correos de la startup vía el SMTP corporativo (Titan/GoDaddy):
bienvenidas, códigos de verificación, recuperación de contraseña y alertas.

Diseño:
- Usa SOLO la stdlib (`smtplib` + `email`) -> sin dependencias nuevas, imagen ligera.
- Puerto 465 => SMTP_SSL (conexión TLS implícita). Puerto 587 => STARTTLS.
- El envío es bloqueante; se ejecuta en un thread (`asyncio.to_thread`) para no
  bloquear el event loop de FastAPI.
- Best-effort: `send_email` nunca lanza; devuelve True/False y loguea. Un fallo de
  correo JAMÁS debe romper un registro/login. Los flujos que necesiten garantía
  deben revisar el valor de retorno.

Configuración por variables de entorno (inyectadas desde Secrets Manager en prod):
    SMTP_HOST      p.ej. smtp.titan.email
    SMTP_PORT      465 (SSL) | 587 (STARTTLS)
    SMTP_USER      atencion.al.cliente@xuve.net
    SMTP_PASSWORD  (secreto)
    SMTP_FROM      remitente visible (por defecto = SMTP_USER)
    SMTP_FROM_NAME nombre visible del remitente (por defecto "Xuve")
"""

import os
import ssl
import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

logger = logging.getLogger(__name__)


def _config() -> dict:
    """Lee la configuración SMTP del entorno (en cada envío, para no cachear
    valores antes de que Secrets Manager los inyecte)."""
    return {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": int(os.environ.get("SMTP_PORT", "465")),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_addr": os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER", ""),
        "from_name": os.environ.get("SMTP_FROM_NAME", "Xuve"),
        # Configuration set de SES (opcional): habilita supresión + eventos de
        # bounce/complaint por correo. Si está vacío, no se añade la cabecera.
        "ses_config_set": os.environ.get("SES_CONFIGURATION_SET", ""),
    }


def is_configured() -> bool:
    """True si hay credenciales SMTP suficientes para intentar un envío."""
    c = _config()
    return bool(c["host"] and c["user"] and c["password"])


def _send_blocking(
    to: str, subject: str, html: str, text: str | None, cfg: dict
) -> None:
    """Construye y envía el mensaje de forma síncrona (corre en un thread)."""
    msg = EmailMessage()
    msg["From"] = formataddr((cfg["from_name"], cfg["from_addr"]))
    msg["To"] = to
    msg["Subject"] = subject
    # Asocia el envío a un configuration set de SES (supresión + eventos SNS).
    if cfg.get("ses_config_set"):
        msg["X-SES-CONFIGURATION-SET"] = cfg["ses_config_set"]
    # Cuerpo: texto plano de respaldo + HTML.
    msg.set_content(text or "Este mensaje requiere un cliente compatible con HTML.")
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    if cfg["port"] == 465:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=context, timeout=15) as s:
            s.login(cfg["user"], cfg["password"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as s:
            s.starttls(context=context)
            s.login(cfg["user"], cfg["password"])
            s.send_message(msg)


async def send_email(
    to: str, subject: str, html: str, text: str | None = None
) -> bool:
    """Envía un correo. Best-effort: nunca lanza, devuelve True si se envió.

    Si SMTP no está configurado, no falla: loguea y devuelve False (útil en
    local/tests donde no queremos enviar correos reales)."""
    cfg = _config()
    if not (cfg["host"] and cfg["user"] and cfg["password"]):
        logger.info("SMTP no configurado; se omite envío de correo a %s", to)
        return False
    try:
        await asyncio.to_thread(_send_blocking, to, subject, html, text, cfg)
        logger.info("Correo enviado a %s (asunto: %s)", to, subject)
        return True
    except Exception as exc:  # noqa: BLE001 - best-effort, no debe propagar
        logger.warning("Fallo al enviar correo a %s: %s", to, exc)
        return False


# ---------------------------------------------------------------------------
# Plantillas de los correos de la startup.
# ---------------------------------------------------------------------------
_BRAND = "Xuve"
_FOOTER = (
    '<hr style="border:none;border-top:1px solid #eee;margin:24px 0">'
    '<p style="color:#888;font-size:12px">Este es un correo automático de '
    f"{_BRAND}. Si no reconoces esta actividad, ignóralo.</p>"
)


def _wrap(inner: str) -> str:
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;'
        'margin:0 auto;padding:24px;color:#222">'
        f'<h2 style="color:#0a7d3b;margin:0 0 16px">{_BRAND}</h2>'
        f"{inner}{_FOOTER}</div>"
    )


async def send_welcome_email(to: str, name: str) -> bool:
    """Correo de bienvenida a un nuevo usuario."""
    safe_name = (name or "").strip() or "¡Hola!"
    html = _wrap(
        f"<p>Hola <b>{safe_name}</b>,</p>"
        f"<p>¡Bienvenido a {_BRAND}! Tu cuenta se creó correctamente y ya puedes "
        "empezar a usar el ecosistema.</p>"
        "<p>Gracias por sumarte.</p>"
    )
    text = f"Hola {safe_name}, ¡bienvenido a {_BRAND}! Tu cuenta se creó correctamente."
    return await send_email(to, f"Bienvenido a {_BRAND}", html, text)


async def send_verification_email(to: str, code: str) -> bool:
    """Correo con código de verificación de registro."""
    html = _wrap(
        "<p>Tu código de verificación es:</p>"
        f'<p style="font-size:28px;font-weight:bold;letter-spacing:4px;'
        f'color:#0a7d3b">{code}</p>'
        "<p>El código caduca en 15 minutos.</p>"
    )
    text = f"Tu código de verificación de {_BRAND} es: {code} (caduca en 15 minutos)."
    return await send_email(to, f"Tu código de verificación · {_BRAND}", html, text)


async def send_password_reset_email(to: str, reset_link: str) -> bool:
    """Correo de recuperación de contraseña con enlace."""
    html = _wrap(
        "<p>Recibimos una solicitud para restablecer tu contraseña.</p>"
        f'<p><a href="{reset_link}" style="background:#0a7d3b;color:#fff;'
        'padding:10px 18px;border-radius:6px;text-decoration:none">'
        "Restablecer contraseña</a></p>"
        "<p>Si no fuiste tú, ignora este correo. El enlace caduca en 1 hora.</p>"
    )
    text = f"Restablece tu contraseña de {_BRAND}: {reset_link} (caduca en 1 hora)."
    return await send_email(to, f"Recupera tu contraseña · {_BRAND}", html, text)

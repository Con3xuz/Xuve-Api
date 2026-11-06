from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse
from datetime import datetime, timezone
import uuid
import os

from utils.auth import get_current_user
from utils import storage

# Rate limiting (instancia compartida)
from utils.ratelimit import limiter

def _is_real_image(data: bytes) -> bool:
    """Verifica los magic bytes: JPEG, PNG, GIF o WEBP (RIFF...WEBP)."""
    if len(data) < 12:
        return False
    if data[:3] == b"\xff\xd8\xff":  # JPEG
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":  # PNG
        return True
    if data[:6] in (b"GIF87a", b"GIF89a"):  # GIF
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":  # WEBP
        return True
    return False


# Router for upload operations
router = APIRouter(prefix="/upload", tags=["Upload"])

# Separate router for serving static uploads (no prefix)
uploads_router = APIRouter(tags=["Uploads Static"])


@router.post("/image")
@limiter.limit("10/minute")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """
    Sube un archivo de imagen. REQUIERE sesión válida (auth obligatoria) y está
    limitada por rate-limit (10/min por IP). Se guarda en S3 privado (prod) o en
    disco local (dev). Acepta multipart/form-data con un campo 'file'.
    """
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido. Permitidos: {', '.join(allowed_types)}",
        )

    # Validate file size (max 5MB)
    contents = await file.read()
    max_size = 5 * 1024 * 1024  # 5MB
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400, detail="El archivo es muy grande. Máximo 5MB"
        )

    # Defensa: el content_type del cliente es falsificable. Validamos los magic
    # bytes reales del archivo para confirmar que es una imagen de verdad.
    if not _is_real_image(contents):
        raise HTTPException(
            status_code=400, detail="El archivo no es una imagen válida"
        )

    # Generate unique filename (extensión saneada a un set conocido).
    raw_ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "jpg"
    ext = raw_ext if raw_ext in {"jpg", "jpeg", "png", "webp", "gif"} else "jpg"
    unique_filename = (
        f"{uuid.uuid4().hex[:16]}_{int(datetime.now(timezone.utc).timestamp())}.{ext}"
    )

    # Guarda en S3 (prod) o disco local (dev) según configuración.
    storage.save_image(unique_filename, contents, file.content_type)

    return {
        "url": f"/api/uploads/{unique_filename}",
        "filename": unique_filename,
        "content_type": file.content_type,
        "size": len(contents),
        "uploaded_by": user["user_id"],
        "storage": "s3" if storage.is_s3_enabled() else "local",
    }


@uploads_router.get("/uploads/{filename}")
async def get_uploaded_file(filename: str):
    """Sirve un archivo subido. En S3 redirige a una URL prefirmada temporal."""
    # Defensa contra path traversal: solo nombre de archivo plano.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")

    if storage.is_s3_enabled():
        # El objeto en S3 es privado: se entrega vía URL prefirmada temporal.
        return RedirectResponse(url=storage.get_presigned_url(filename), status_code=307)

    # Fallback local (dev): sirve el archivo del disco, validando la ruta.
    file_path = storage.local_path(filename)
    real_base = os.path.realpath(storage.LOCAL_DIR)
    if os.path.commonpath([os.path.realpath(file_path), real_base]) != real_base:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    ext = filename.split(".")[-1].lower()
    content_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    content_type = content_types.get(ext, "application/octet-stream")
    return FileResponse(file_path, media_type=content_type)

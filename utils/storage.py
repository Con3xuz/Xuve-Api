"""
Almacenamiento de archivos — S3 privado (producción) con fallback a disco (dev).
================================================================================
Si `S3_BUCKET` está configurado, los archivos (incl. documentos KYC) se guardan
en un bucket S3 PRIVADO y se sirven con URLs prefirmadas temporales. Así:
  - NO se pierden en cada despliegue del contenedor (antes vivían en disco efímero).
  - NO quedan públicos (el bucket bloquea acceso público; se accede vía presigned).
Sin `S3_BUCKET` (dev local), cae a disco local en LOCAL_DIR.

Credenciales: en prod, el rol de instancia EC2 (XuveEC2Role); en local, el AWS CLI.
"""

import os

S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_PREFIX = "uploads/"
LOCAL_DIR = "/app/backend/uploads"

_s3_client = None


def is_s3_enabled() -> bool:
    return bool(S3_BUCKET)


def _client():
    global _s3_client
    if _s3_client is None:
        import boto3  # import perezoso: solo se carga si se usa S3

        _s3_client = boto3.client("s3", region_name=S3_REGION)
    return _s3_client


def save_image(filename: str, content: bytes, content_type: str) -> None:
    """Guarda el archivo en S3 (si está habilitado) o en disco local (dev)."""
    if is_s3_enabled():
        _client().put_object(
            Bucket=S3_BUCKET,
            Key=f"{S3_PREFIX}{filename}",
            Body=content,
            ContentType=content_type,
        )
    else:
        os.makedirs(LOCAL_DIR, exist_ok=True)
        with open(os.path.join(LOCAL_DIR, filename), "wb") as f:
            f.write(content)


def get_presigned_url(filename: str, expires: int = 3600) -> str:
    """URL prefirmada temporal (GET) para leer un objeto privado de S3."""
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": f"{S3_PREFIX}{filename}"},
        ExpiresIn=expires,
    )


def local_path(filename: str) -> str:
    return os.path.join(LOCAL_DIR, filename)

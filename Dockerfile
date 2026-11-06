# Imagen de producción LIGERA del backend Xuve (FastAPI) para AWS App Runner.
# Instala solo las dependencias realmente importadas por el código.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Set mínimo de dependencias (sin compiladores: todas tienen wheels manylinux).
COPY requirements-runtime.txt .
RUN pip install --upgrade pip && pip install -r requirements-runtime.txt

COPY . .

# App Runner enruta al puerto expuesto. Por defecto 8080.
EXPOSE 8080

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]

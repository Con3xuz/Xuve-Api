"""
Integración KYC Progresivo + Métodos de Pago (xuve-kyc-service).
================================================================
A diferencia del resto de la suite (que golpea un servidor vivo vía
REACT_APP_BACKEND_URL), estos tests son autocontenidos:

- Levantan el microservicio REAL xuve-kyc-service como subproceso (uvicorn en
  127.0.0.1:8017) con API key y secreto HMAC de prueba, así se ejercita de
  verdad la autenticación X-KYC-API-KEY y la firma X-KYC-Signature.
- Ejecutan el backend principal in-process (fastapi TestClient) con una BD
  fake en memoria (Postgres no es necesario).

Flujos cubiertos:
1. Registro progresivo: solo teléfono + nombre + correo; nace activo.
2. Gate del primer viaje: 403 PAYMENT_METHOD_REQUIRED sin método validado.
3. Proxy de pre-validación en vivo (200 canónico / 422 con errores).
4. Registro de método de pago: 412 sin identidad verificada; MATCH→201 ACTIVE;
   MANUAL_REVIEW→202 PENDING_VALIDATION; MISMATCH→400 (cláusula 3.2);
   3 strikes→403 SUSPEND_ACCOUNT con revocación de JWT.
5. Instrumento duplicado en otra cuenta → 409.

Si el directorio del microservicio no existe (otra máquina), la suite se salta.
Ruta configurable con XUVE_KYC_SERVICE_DIR.
"""

import copy
import hashlib
import hmac
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Entorno ANTES de importar el backend (los módulos leen env al importarse).
# load_dotenv no pisa variables ya presentes, así que estas ganan al .env.
# ─────────────────────────────────────────────────────────────────────────────
KYC_TEST_PORT = int(os.environ.get("XUVE_KYC_TEST_PORT", "8017"))
KYC_TEST_API_KEY = "test-integration-key"
KYC_TEST_HMAC_SECRET = "test-hmac-secret"

os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["JWT_SECRET"] = "jwt-secret-solo-para-tests-de-integracion"
os.environ["KYC_SERVICE_URL"] = f"http://127.0.0.1:{KYC_TEST_PORT}"
os.environ["KYC_SERVICE_API_KEY"] = KYC_TEST_API_KEY
os.environ["KYC_SERVICE_HMAC_SECRET"] = KYC_TEST_HMAC_SECRET
os.environ["PAYMENT_METHOD_GATE_ENABLED"] = "true"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

# Directorio del microservicio: por defecto, hermano del repo en d:\PROYECTOS.
KYC_SERVICE_DIR = Path(
    os.environ.get("XUVE_KYC_SERVICE_DIR", str(BACKEND_DIR.parents[2] / "XUVE KYC"))
)

pytestmark = pytest.mark.skipif(
    not KYC_SERVICE_DIR.exists(),
    reason=f"xuve-kyc-service no encontrado en {KYC_SERVICE_DIR} (define XUVE_KYC_SERVICE_DIR)",
)


# ─────────────────────────────────────────────────────────────────────────────
# BD fake en memoria (subset de la API Mongo que usan los endpoints tocados)
# ─────────────────────────────────────────────────────────────────────────────
def _match_value(doc_value, expected) -> bool:
    if isinstance(expected, dict):
        for op, arg in expected.items():
            if op == "$in":
                if doc_value not in arg:
                    return False
            elif op == "$ne":
                if doc_value == arg:
                    return False
            elif op == "$nin":
                if doc_value in arg:
                    return False
            else:
                raise NotImplementedError(f"Operador no soportado en fake DB: {op}")
        return True
    return doc_value == expected


def _matches(doc: dict, flt: dict) -> bool:
    return all(_match_value(doc.get(k), v) for k, v in (flt or {}).items())


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction=-1):
        self._docs.sort(key=lambda d: d.get(key) or "", reverse=direction == -1)
        return self

    async def to_list(self, n):
        return [copy.deepcopy(d) for d in self._docs[:n]]


class FakeCollection:
    def __init__(self):
        self._docs: list[dict] = []

    async def find_one(self, flt, projection=None, sort=None):
        docs = [d for d in self._docs if _matches(d, flt)]
        if sort:
            key, direction = sort[0]
            docs.sort(key=lambda d: d.get(key) or "", reverse=direction == -1)
        return copy.deepcopy(docs[0]) if docs else None

    def find(self, flt=None, projection=None):
        return _FakeCursor([copy.deepcopy(d) for d in self._docs if _matches(d, flt)])

    async def insert_one(self, doc):
        self._docs.append(copy.deepcopy(doc))

    async def update_one(self, flt, update, upsert=False):
        for doc in self._docs:
            if _matches(doc, flt):
                self._apply(doc, update)
                return
        if upsert:
            base = {k: v for k, v in flt.items() if not isinstance(v, dict)}
            self._apply(base, update)
            self._docs.append(base)

    async def delete_many(self, flt):
        self._docs[:] = [d for d in self._docs if not _matches(d, flt)]

    async def delete_one(self, flt):
        for i, d in enumerate(self._docs):
            if _matches(d, flt):
                del self._docs[i]
                return

    @staticmethod
    def _apply(doc: dict, update: dict) -> None:
        for key, value in update.get("$set", {}).items():
            doc[key] = copy.deepcopy(value)
        for key in update.get("$unset", {}):
            doc.pop(key, None)
        for key, delta in update.get("$inc", {}).items():
            doc[key] = doc.get(key, 0) + delta


FAKE_COLLECTIONS = [
    "users",
    "user_sessions",
    "email_verifications",
    "kyc_requests",
    "payment_methods",
    "services",
]


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def kyc_service():
    """Levanta el xuve-kyc-service real con credenciales de prueba."""
    venv_python = KYC_SERVICE_DIR / ".venv" / "Scripts" / "python.exe"
    python = str(venv_python) if venv_python.exists() else sys.executable

    env = dict(os.environ)
    env.update(
        {
            "APP_ENV": "test",
            "LOG_LEVEL": "WARNING",
            "KYC_API_KEY": KYC_TEST_API_KEY,
            "HMAC_SIGNING_SECRET": KYC_TEST_HMAC_SECRET,
            # Obligatoria para el arranque; los endpoints de titularidad no la usan.
            "OPENROUTER_API_KEY": "dummy-key-for-integration-tests",
        }
    )
    proc = subprocess.Popen(
        [
            python,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(KYC_TEST_PORT),
        ],
        cwd=str(KYC_SERVICE_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 40
        last_error = None
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail("xuve-kyc-service terminó de forma inesperada al arrancar")
            try:
                resp = httpx.get(
                    f"http://127.0.0.1:{KYC_TEST_PORT}/api/v1/health", timeout=2
                )
                if resp.status_code == 200:
                    break
            except httpx.HTTPError as exc:
                last_error = exc
            time.sleep(0.5)
        else:
            pytest.fail(f"xuve-kyc-service no respondió el health check: {last_error}")
        yield f"http://127.0.0.1:{KYC_TEST_PORT}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="module")
def client(kyc_service):
    """Backend principal in-process con BD fake y startup de Postgres anulado."""
    import server
    import utils.database as dbmod

    async def _noop():
        return None

    server.init_db = _noop
    server.close_db = _noop

    for name in FAKE_COLLECTIONS:
        setattr(dbmod.db, name, FakeCollection())

    with TestClient(server.app) as test_client:
        yield test_client


def _users_collection() -> FakeCollection:
    import utils.database as dbmod

    return dbmod.db.users


def _register(client: TestClient, name: str = "Maria Carolina Perez Gomez"):
    """Registro progresivo: solo correo + nombre + teléfono (+ contraseña)."""
    unique = uuid.uuid4().hex[:10]
    payload = {
        "email": f"test_{unique}@xuve.net",
        "password": "clave-segura-123",
        "name": name,
        "phone": f"+58414{unique[:7]}",
    }
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["user"], data["token"]


def _grant_verified_identity(user_id: str, id_number: str, full_name: str):
    """Simula un KYC de identidad aprobado: inyecta el snapshot en la BD fake."""
    for doc in _users_collection()._docs:
        if doc["user_id"] == user_id:
            doc["verified_identity"] = {
                "kyc_request_id": f"req_{uuid.uuid4().hex[:16]}",
                "entity_type": "CUSTOMER",
                "id_number": id_number,
                "full_name": full_name,
            }
            doc["kyc_status"] = "approved"
            return
    raise AssertionError(f"Usuario {user_id} no encontrado en la BD fake")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _pago_movil(cedula: str, name: str, phone: str) -> dict:
    return {
        "method_type": "PAGO_MOVIL",
        "holder_full_name": name,
        "holder_id_number": cedula,
        "bank_code": "0102",
        "phone_number": phone,
    }


RIDE_PAYLOAD = {
    "service_type": "movilidad",
    "pickup_lat": 10.4806,
    "pickup_lng": -66.9036,
    "pickup_address": "Plaza Venezuela",
    "dropoff_lat": 10.5061,
    "dropoff_lng": -66.9146,
    "dropoff_address": "Los Palos Grandes",
}


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────
class TestKYCServiceContract:
    def test_health_and_hmac_signature(self, kyc_service):
        """El microservicio firma TODA respuesta con HMAC-SHA256 verificable."""
        resp = httpx.get(f"{kyc_service}/api/v1/health", timeout=5)
        assert resp.status_code == 200
        signature = resp.headers.get("X-KYC-Signature")
        assert signature, "Falta el header X-KYC-Signature"
        expected = hmac.new(
            KYC_TEST_HMAC_SECRET.encode(), resp.content, hashlib.sha256
        ).hexdigest()
        assert hmac.compare_digest(expected, signature)

    def test_rejects_missing_api_key(self, kyc_service):
        resp = httpx.post(
            f"{kyc_service}/api/v1/payment-methods/pre-validate",
            json={"method_type": "PAGO_MOVIL"},
            timeout=5,
        )
        assert resp.status_code == 401


class TestProgressiveRegistration:
    def test_register_minimal_data_born_active(self, client):
        user, token = self._register_and_check(client)
        # Puede explorar la app: /me responde con la sesión recién emitida.
        me = client.get("/api/auth/me", headers=_auth(token))
        assert me.status_code == 200
        assert me.json()["user_id"] == user["user_id"]

    @staticmethod
    def _register_and_check(client):
        user, token = _register(client)
        assert user["role"] == "user"
        assert user["status"] == "active"
        assert user["kyc_status"] == "pending"  # sin fricción, pero sin verificar
        return user, token

    def test_first_ride_blocked_without_payment_method(self, client):
        _, token = _register(client)
        resp = client.post("/api/services/request", json=RIDE_PAYLOAD, headers=_auth(token))
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["error_code"] == "PAYMENT_METHOD_REQUIRED"


class TestPreValidationProxy:
    def test_requires_auth(self, client):
        resp = client.post(
            "/api/v1/user/payment-methods/pre-validate",
            json={"method_type": "PAGO_MOVIL"},
        )
        assert resp.status_code == 401

    def test_valid_draft_returns_canonical_data(self, client):
        _, token = _register(client)
        resp = client.post(
            "/api/v1/user/payment-methods/pre-validate",
            json=_pago_movil("V-12.345.678", "Maria Carolina Perez Gomez", "0414-1234567"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["valid"] is True
        formatted = body["formatted_data"]
        # Formas canónicas listas para el registro definitivo.
        assert formatted["holder_id_number"] == "V12345678"
        assert formatted["phone_number"] == "4141234567"
        assert formatted["holder_full_name"] == "MARIA CAROLINA PEREZ GOMEZ"

    def test_invalid_draft_returns_field_errors(self, client):
        _, token = _register(client)
        resp = client.post(
            "/api/v1/user/payment-methods/pre-validate",
            json=_pago_movil("12345678", "Maria Perez", "1234"),  # sin prefijo y tel. inválido
            headers=_auth(token),
        )
        assert resp.status_code == 422, resp.text
        body = resp.json()
        assert body["valid"] is False
        fields_with_errors = {e["field"] for e in body["errors"]}
        assert "holder_id_number" in fields_with_errors or "phone_number" in fields_with_errors


class TestPaymentMethodRegistration:
    def test_requires_verified_identity(self, client):
        _, token = _register(client)
        resp = client.post(
            "/api/v1/user/payment-methods",
            json=_pago_movil("V-12345678", "Maria Carolina Perez Gomez", "0414-1234567"),
            headers=_auth(token),
        )
        assert resp.status_code == 412, resp.text
        assert resp.json()["error_code"] == "KYC_REQUIRED"

    def test_match_creates_active_and_unlocks_first_ride(self, client):
        user, token = _register(client, name="Maria Carolina Perez Gomez")
        _grant_verified_identity(user["user_id"], "V-12345678", "MARIA CAROLINA PEREZ GOMEZ")

        resp = client.post(
            "/api/v1/user/payment-methods",
            json=_pago_movil("V-12345678", "Maria Carolina Perez Gomez", "0414-1234567"),
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        method = resp.json()["payment_method"]
        assert method["status"] == "ACTIVE"
        assert method["method_type"] == "PAGO_MOVIL"
        # El instrumento no viaja en claro: solo la vista enmascarada.
        assert "1234567" not in (method["masked_identifier"] or "").replace("*", "x")[:-4]

        listed = client.get("/api/v1/user/payment-methods", headers=_auth(token))
        assert listed.status_code == 200
        assert len(listed.json()["payment_methods"]) == 1

        # El gate del primer viaje se abre con el método ACTIVE.
        ride = client.post("/api/services/request", json=RIDE_PAYLOAD, headers=_auth(token))
        assert ride.status_code == 200, ride.text
        assert ride.json()["service_id"].startswith("srv_")

    def test_manual_review_returns_202_pending_validation(self, client):
        """Cédula correcta con nombre divergente: revisión manual, sin strike."""
        user, token = _register(client, name="Ana Isabel Fernandez Blanco")
        _grant_verified_identity(user["user_id"], "V-22333444", "ANA ISABEL FERNANDEZ BLANCO")

        resp = client.post(
            "/api/v1/user/payment-methods",
            json=_pago_movil("V-22333444", "Jose Rafael Rodriguez Silva", "0424-7654321"),
            headers=_auth(token),
        )
        assert resp.status_code == 202, resp.text
        assert resp.json()["payment_method"]["status"] == "PENDING_VALIDATION"

        # PENDING_VALIDATION no abre el gate: el instrumento aún no es utilizable.
        ride = client.post("/api/services/request", json=RIDE_PAYLOAD, headers=_auth(token))
        assert ride.status_code == 403

    def test_three_strikes_suspend_account_and_revoke_jwt(self, client):
        """Cláusula 6: 3 MISMATCH en 24h → suspensión + revocación de sesiones."""
        user, token = _register(client, name="Pedro Luis Marquez Rojas")
        _grant_verified_identity(user["user_id"], "V-5666777", "PEDRO LUIS MARQUEZ ROJAS")

        foreign = _pago_movil("V-99888777", "Otra Persona Cualquiera", "0412-5556677")

        first = client.post("/api/v1/user/payment-methods", json=foreign, headers=_auth(token))
        assert first.status_code == 400, first.text
        body = first.json()
        assert body["error_code"] == "OWNERSHIP_MISMATCH"
        assert "3.2" in body["tc_clauses"]
        assert body["remaining_attempts"] == 2

        second = client.post("/api/v1/user/payment-methods", json=foreign, headers=_auth(token))
        assert second.status_code == 400
        assert second.json()["remaining_attempts"] == 1

        third = client.post("/api/v1/user/payment-methods", json=foreign, headers=_auth(token))
        assert third.status_code == 403, third.text
        body = third.json()
        assert body["error_code"] == "ACCOUNT_SUSPENDED"
        assert body["account_status"] == "SUSPENDED_PENDING_REVIEW"
        assert "6" in body["tc_clauses"]

        # Estado persistido en la cuenta.
        doc = next(
            d for d in _users_collection()._docs if d["user_id"] == user["user_id"]
        )
        assert doc["status"] == "suspended"
        assert doc["account_status"] == "SUSPENDED_PENDING_REVIEW"
        assert doc["token_version"] == 1

        # El JWT emitido antes de la suspensión queda revocado (token_version).
        me = client.get("/api/auth/me", headers=_auth(token))
        assert me.status_code == 401

    def test_same_instrument_in_another_account_conflicts(self, client):
        """La huella SHA-256 detecta el mismo instrumento en cuentas distintas."""
        user, token = _register(client, name="Carmen Elena Torres Diaz")
        _grant_verified_identity(user["user_id"], "V-31415926", "CARMEN ELENA TORRES DIAZ")

        # Mismo teléfono + banco que el instrumento ACTIVE del test de MATCH,
        # aunque el titular declarado coincida con la identidad de esta cuenta.
        resp = client.post(
            "/api/v1/user/payment-methods",
            json=_pago_movil("V-31415926", "Carmen Elena Torres Diaz", "0414-1234567"),
            headers=_auth(token),
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["error_code"] == "INSTRUMENT_ALREADY_REGISTERED"


class TestRoleDossierGuards:
    """Guardas del backend para los expedientes driver/merchant (la verificación
    completa con OCR/biometría requiere la API key real del motor de IA)."""

    def test_requires_auth(self, client):
        resp = client.post("/api/kyc/verify/driver")
        assert resp.status_code == 401

    def test_driver_dossier_rejects_invalid_role(self, client):
        _, token = _register(client)
        fake_file = ("doc.jpg", b"x", "image/jpeg")
        resp = client.post(
            "/api/kyc/verify/driver",
            data={"requested_role": "socio_comercial"},  # rol de comercio, no de conductor
            files={
                "document_front": fake_file,
                "liveness_video": ("v.mp4", b"x", "video/mp4"),
                "driver_license": fake_file,
                "vehicle_card": fake_file,
                "vehicle_photo": fake_file,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400
        assert "expediente de conductor" in resp.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

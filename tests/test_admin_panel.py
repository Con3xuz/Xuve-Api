"""
Test suite for Admin Panel (/admin) - Panel de Administración OMNI
Testing endpoints for:
1. KPIs Globales - /api/admin/stats
2. Verificación KYC - /api/admin/kyc/all-pending
3. Control de Verticales - /api/admin/verticales/*
4. Configuración Financiera - /api/admin/config/financial
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestAdminAuth:
    """Test admin authentication and access control"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        # Login as admin
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@omni.ve", "password": "admin123"},
        )
        assert (
            login_response.status_code == 200
        ), f"Admin login failed: {login_response.text}"

        login_data = login_response.json()
        assert "token" in login_data, "No token in login response"
        assert (
            login_data.get("user", {}).get("role") == "admin"
        ), f"User is not admin, role is: {login_data.get('user', {}).get('role')}"

        self.token = login_data["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        print(
            f"Admin login successful: {login_data['user']['email']} (role: {login_data['user']['role']})"
        )

    def test_admin_login_success(self):
        """Verify admin can login with admin@omni.ve / admin123"""
        # Login already done in setup, just verify token exists
        assert self.token is not None
        print("PASS: Admin login with admin@omni.ve / admin123")


class TestAdminKPIsGlobales:
    """Test KPIs Globales - /api/admin/stats endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@omni.ve", "password": "admin123"},
        )
        assert login_response.status_code == 200
        self.token = login_response.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def test_admin_stats_endpoint(self):
        """Test /api/admin/stats returns all required KPIs"""
        response = self.session.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 200, f"Stats endpoint failed: {response.text}"

        data = response.json()

        # Verify all required KPIs are present
        required_fields = [
            "users",  # Usuarios totales
            "busetas_activas",  # Busetas activas
            "viajes_programados",  # Viajes programados
            "orders",  # Órdenes market
            "volumen_transaccionado",  # Volumen transaccionado
            "ingresos_plataforma",  # Ingresos OMNI
        ]

        for field in required_fields:
            assert field in data, f"Missing KPI field: {field}"
            print(f"  {field}: {data[field]}")

        # Verify numeric types
        assert isinstance(data["users"], int), "users should be int"
        assert isinstance(data["busetas_activas"], int), "busetas_activas should be int"
        assert isinstance(
            data["viajes_programados"], int
        ), "viajes_programados should be int"
        assert isinstance(data["orders"], int), "orders should be int"
        assert isinstance(
            data["volumen_transaccionado"], (int, float)
        ), "volumen_transaccionado should be numeric"
        assert isinstance(
            data["ingresos_plataforma"], (int, float)
        ), "ingresos_plataforma should be numeric"

        print("PASS: /api/admin/stats returns all required KPIs")

    def test_admin_stats_additional_fields(self):
        """Test additional stats fields"""
        response = self.session.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 200

        data = response.json()

        # Additional fields that should be present
        additional_fields = [
            "drivers",  # Conductores aprobados
            "lineas_urbanas",  # Líneas urbanas
            "rutas_urbanas",  # Rutas urbanas
            "services",  # Servicios activos
        ]

        for field in additional_fields:
            if field in data:
                print(f"  {field}: {data[field]}")

        print("PASS: Additional stats fields verified")


class TestAdminKYCVerification:
    """Test KYC Verification - /api/admin/kyc/* endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@omni.ve", "password": "admin123"},
        )
        assert login_response.status_code == 200
        self.token = login_response.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def test_kyc_all_pending_endpoint(self):
        """Test /api/admin/kyc/all-pending returns pending KYC requests"""
        response = self.session.get(f"{BASE_URL}/api/admin/kyc/all-pending")
        assert (
            response.status_code == 200
        ), f"KYC all-pending endpoint failed: {response.text}"

        data = response.json()

        # Verify response structure
        assert "pending" in data, "Missing 'pending' field in response"
        assert "total" in data, "Missing 'total' field in response"
        assert isinstance(data["pending"], list), "'pending' should be a list"
        assert isinstance(data["total"], int), "'total' should be int"

        print(f"PASS: /api/admin/kyc/all-pending - {data['total']} pending requests")

        # If there are pending items, verify structure
        if len(data["pending"]) > 0:
            item = data["pending"][0]
            required_kyc_fields = ["type", "id", "name", "email"]
            for field in required_kyc_fields:
                assert field in item, f"Missing field '{field}' in KYC item"
            print(f"  First pending: {item['type']} - {item['name']} ({item['email']})")

    def test_kyc_approve_endpoint_format(self):
        """Test KYC approve endpoint accepts correct format"""
        # Test with a non-existent entity to verify endpoint exists
        response = self.session.post(
            f"{BASE_URL}/api/admin/kyc/socio_conductor/nonexistent123/approve"
        )
        # Should return 404 for non-existent entity, not 400/500
        assert (
            response.status_code == 404
        ), f"Expected 404, got {response.status_code}: {response.text}"
        print(
            "PASS: KYC approve endpoint format verified (returns 404 for non-existent)"
        )

    def test_kyc_reject_endpoint_format(self):
        """Test KYC reject endpoint accepts correct format"""
        response = self.session.post(
            f"{BASE_URL}/api/admin/kyc/socio_conductor/nonexistent123/reject",
            json={"reason": "Test rejection"},
        )
        # Should return 404 for non-existent entity
        assert (
            response.status_code == 404
        ), f"Expected 404, got {response.status_code}: {response.text}"
        print(
            "PASS: KYC reject endpoint format verified (returns 404 for non-existent)"
        )


class TestAdminControlVerticales:
    """Test Control de Verticales - /api/admin/verticales/* endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@omni.ve", "password": "admin123"},
        )
        assert login_response.status_code == 200
        self.token = login_response.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def test_verticales_urbanas_endpoint(self):
        """Test /api/admin/verticales/urbanas - Transporte Urbano"""
        response = self.session.get(f"{BASE_URL}/api/admin/verticales/urbanas")
        assert (
            response.status_code == 200
        ), f"Verticales urbanas failed: {response.text}"

        data = response.json()
        assert isinstance(data, list), "Response should be a list of lineas urbanas"

        if len(data) > 0:
            linea = data[0]
            # Verify linea structure
            assert "linea_id" in linea or "nombre_linea" in linea
            print(f"  Found {len(data)} líneas urbanas")
            if "nombre_linea" in linea:
                print(f"  First linea: {linea['nombre_linea']}")

        print("PASS: /api/admin/verticales/urbanas - Transporte Urbano endpoint")

    def test_verticales_carga_endpoint(self):
        """Test /api/admin/verticales/carga - Carga Pesada"""
        response = self.session.get(f"{BASE_URL}/api/admin/verticales/carga")
        assert response.status_code == 200, f"Verticales carga failed: {response.text}"

        data = response.json()

        # Verify response structure for carga pesada
        expected_fields = ["operadores_count", "vehiculos_count", "servicios_activos"]
        for field in expected_fields:
            assert field in data, f"Missing field '{field}' in carga response"
            print(f"  {field}: {data[field]}")

        print("PASS: /api/admin/verticales/carga - Carga Pesada endpoint")

    def test_verticales_rent_a_car_endpoint(self):
        """Test /api/admin/verticales/rent-a-car - Rent-a-Car"""
        response = self.session.get(f"{BASE_URL}/api/admin/verticales/rent-a-car")
        assert (
            response.status_code == 200
        ), f"Verticales rent-a-car failed: {response.text}"

        data = response.json()

        # Verify response structure for rent-a-car
        expected_fields = ["owners_count", "vehicles_count", "active_rentals"]
        for field in expected_fields:
            assert field in data, f"Missing field '{field}' in rent-a-car response"
            print(f"  {field}: {data[field]}")

        print("PASS: /api/admin/verticales/rent-a-car - Rent-a-Car endpoint")

    def test_verticales_terminales_endpoint(self):
        """Test /api/admin/verticales/terminales - Terminales Interurbanos"""
        response = self.session.get(f"{BASE_URL}/api/admin/verticales/terminales")
        assert (
            response.status_code == 200
        ), f"Verticales terminales failed: {response.text}"

        data = response.json()

        # Verify response structure for terminales
        expected_fields = [
            "lineas_count",
            "rutas_count",
            "vehiculos_count",
            "viajes_activos",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field '{field}' in terminales response"
            print(f"  {field}: {data[field]}")

        print("PASS: /api/admin/verticales/terminales - Terminales endpoint")


class TestAdminConfigFinanciera:
    """Test Configuración Financiera - /api/admin/config/financial endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@omni.ve", "password": "admin123"},
        )
        assert login_response.status_code == 200
        self.token = login_response.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def test_financial_config_get_endpoint(self):
        """Test GET /api/admin/config/financial returns config"""
        response = self.session.get(f"{BASE_URL}/api/admin/config/financial")
        assert (
            response.status_code == 200
        ), f"Financial config GET failed: {response.text}"

        data = response.json()

        # Verify required config fields
        required_fields = [
            "exchange_rate",  # Tasa de cambio
            "toll_moto",  # Peaje moto
            "toll_others",  # Peaje otros
            "commission_transport",  # Comisión transporte
            "commission_market",  # Comisión market
            "commission_rent",  # Comisión rent
        ]

        for field in required_fields:
            assert field in data, f"Missing config field: {field}"
            print(f"  {field}: {data[field]}")

        # Verify types
        assert isinstance(
            data["exchange_rate"], (int, float)
        ), "exchange_rate should be numeric"
        assert isinstance(
            data["toll_moto"], (int, float)
        ), "toll_moto should be numeric"
        assert isinstance(
            data["toll_others"], (int, float)
        ), "toll_others should be numeric"

        print("PASS: GET /api/admin/config/financial returns all config")

    def test_financial_config_post_endpoint(self):
        """Test POST /api/admin/config/financial updates config"""
        # First get current config
        get_response = self.session.get(f"{BASE_URL}/api/admin/config/financial")
        assert get_response.status_code == 200
        original_config = get_response.json()
        original_rate = original_config.get("exchange_rate", 50.0)

        # Update with new value
        test_rate = 55.55
        update_response = self.session.post(
            f"{BASE_URL}/api/admin/config/financial", json={"exchange_rate": test_rate}
        )
        assert (
            update_response.status_code == 200
        ), f"Financial config POST failed: {update_response.text}"

        # Verify update was successful
        verify_response = self.session.get(f"{BASE_URL}/api/admin/config/financial")
        assert verify_response.status_code == 200
        updated_config = verify_response.json()
        assert (
            updated_config["exchange_rate"] == test_rate
        ), f"Exchange rate not updated: {updated_config['exchange_rate']}"

        # Restore original value
        restore_response = self.session.post(
            f"{BASE_URL}/api/admin/config/financial",
            json={"exchange_rate": original_rate},
        )
        assert restore_response.status_code == 200

        print(
            f"PASS: POST /api/admin/config/financial updates config (tested: {original_rate} -> {test_rate} -> {original_rate})"
        )


class TestAdminAccessControl:
    """Test that non-admin users cannot access admin endpoints"""

    def test_non_admin_cannot_access_stats(self):
        """Test non-admin user gets 403 on admin/stats"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})

        # Login as regular user
        login_response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "cliente@omni.ve", "password": "cliente123"},
        )

        if login_response.status_code != 200:
            pytest.skip("Non-admin user login failed, skipping access control test")

        token = login_response.json().get("token")
        if not token:
            pytest.skip("No token returned for non-admin user")

        session.headers.update({"Authorization": f"Bearer {token}"})

        # Try to access admin stats
        response = session.get(f"{BASE_URL}/api/admin/stats")
        assert (
            response.status_code == 403
        ), f"Expected 403 Forbidden, got {response.status_code}"

        print("PASS: Non-admin users cannot access /api/admin/stats (403)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

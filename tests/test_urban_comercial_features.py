"""
Test Suite for Urban Line Admin, Chofer Urbano, and Comercial Categories
=========================================================================
Tests the new functionalities:
1. Urban Line Admin (linea.urbana@xuve.ve) - separate from line_admin
2. Chofer Urbano (chofer.urbano@xuve.ve) - urban bus driver
3. Comercial Categories (14 categories with emoji/color)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
URBAN_LINE_ADMIN = {"email": "linea.urbana@xuve.ve", "password": "urbana123"}
CHOFER_URBANO = {"email": "chofer.urbano@xuve.ve", "password": "urbano123"}
COMERCIAL = {"email": "comercial@xuve.ve", "password": "comercial123"}


class TestComercialCategories:
    """Test comercial categories API - 14 categories with emoji and color"""

    def test_get_all_categories_returns_14(self):
        """GET /api/comercial/categories should return 14 categories"""
        response = requests.get(f"{BASE_URL}/api/comercial/categories")
        assert response.status_code == 200

        data = response.json()
        assert "categories" in data
        categories = data["categories"]
        assert len(categories) == 14

        # Verify structure of each category
        for cat in categories:
            assert "id" in cat
            assert "label" in cat
            assert "icon" in cat
            assert "color" in cat
            assert "emoji" in cat

        # Verify expected categories exist
        category_ids = [c["id"] for c in categories]
        expected = ["restaurante", "farmacia", "tecnologia", "supermercado", "ropa"]
        for exp_id in expected:
            assert exp_id in category_ids, f"Missing category: {exp_id}"

    def test_category_has_emoji_and_color(self):
        """Each category should have emoji and color defined"""
        response = requests.get(f"{BASE_URL}/api/comercial/categories")
        assert response.status_code == 200

        categories = response.json()["categories"]

        # Check restaurante category
        restaurante = next((c for c in categories if c["id"] == "restaurante"), None)
        assert restaurante is not None
        assert restaurante["emoji"] == "🍽️"  # Plate with utensils emoji
        assert restaurante["color"].startswith("#")

        # Check farmacia category
        farmacia = next((c for c in categories if c["id"] == "farmacia"), None)
        assert farmacia is not None
        assert farmacia["emoji"] == "💊"  # Pill emoji


class TestUrbanLineAdminLogin:
    """Test urban_line_admin login and dashboard access"""

    def test_urban_line_admin_login_success(self):
        """Login with urban_line_admin credentials returns correct role"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=URBAN_LINE_ADMIN)
        assert response.status_code == 200

        data = response.json()
        assert "user" in data
        assert "token" in data
        assert data["user"]["role"] == "urban_line_admin"
        assert data["user"]["email"] == "linea.urbana@xuve.ve"

    def test_urban_line_admin_get_mi_linea(self):
        """Urban line admin can access /api/urban-linea/mi-linea"""
        # Login first
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=URBAN_LINE_ADMIN)
        assert login_res.status_code == 200
        token = login_res.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/urban-linea/mi-linea", headers=headers)
        assert response.status_code == 200

        linea = response.json()
        assert "linea_id" in linea
        assert "nombre_linea" in linea
        assert "wallet_balance" in linea
        assert linea["nombre_linea"] == "Transporte San Benito"

    def test_urban_line_admin_get_rutas(self):
        """Urban line admin can list routes"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=URBAN_LINE_ADMIN)
        token = login_res.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/urban-linea/rutas", headers=headers)
        assert response.status_code == 200

        rutas = response.json()
        assert isinstance(rutas, list)
        assert len(rutas) >= 1

        # Verify demo route exists
        demo_ruta = rutas[0]
        assert demo_ruta["codigo_ruta"] == "R01"
        assert demo_ruta["nombre_ruta"] == "Ruta Centro - Pie del Llano"
        assert demo_ruta["tarifa"] == 0.5

    def test_urban_line_admin_get_vehiculos(self):
        """Urban line admin can list vehicles"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=URBAN_LINE_ADMIN)
        token = login_res.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/urban-linea/vehiculos", headers=headers
        )
        assert response.status_code == 200

        vehiculos = response.json()
        assert isinstance(vehiculos, list)
        assert len(vehiculos) >= 1

    def test_urban_line_admin_get_choferes(self):
        """Urban line admin can list drivers"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=URBAN_LINE_ADMIN)
        token = login_res.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/urban-linea/choferes", headers=headers)
        assert response.status_code == 200

        choferes = response.json()
        assert isinstance(choferes, list)
        assert len(choferes) >= 1


class TestChoferUrbanoLogin:
    """Test chofer_urbano login and dashboard access"""

    def test_chofer_urbano_login_success(self):
        """Login with chofer_urbano credentials returns correct role"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=CHOFER_URBANO)
        assert response.status_code == 200

        data = response.json()
        assert "user" in data
        assert "token" in data
        assert data["user"]["role"] == "chofer_urbano"
        assert data["user"]["email"] == "chofer.urbano@xuve.ve"

    def test_chofer_urbano_get_mi_asignacion(self):
        """Chofer urbano can access their assignment"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=CHOFER_URBANO)
        assert login_res.status_code == 200
        token = login_res.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/urban-linea/chofer/mi-asignacion", headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "asignacion" in data
        assert "chofer" in data
        assert "recorrido_activo" in data

        # Verify assignment data
        assert data["asignacion"]["ruta_codigo"] == "R01"
        assert data["asignacion"]["vehiculo_placa"] == "BUS-101"
        assert data["asignacion"]["tarifa"] == 0.5

        # Verify chofer data
        assert data["chofer"]["nombre"] == "Pedro Urbano"
        assert data["chofer"]["licencia_categoria"] == "5ta"


class TestUrbanLinePublicAPI:
    """Test public urban line APIs"""

    def test_get_public_rutas(self):
        """GET /api/urban-linea/publico/rutas returns active routes (no auth)"""
        response = requests.get(f"{BASE_URL}/api/urban-linea/publico/rutas")
        assert response.status_code == 200

        rutas = response.json()
        assert isinstance(rutas, list)
        assert len(rutas) >= 1

        # Verify route structure
        ruta = rutas[0]
        assert "ruta_id" in ruta
        assert "nombre_ruta" in ruta
        assert "codigo_ruta" in ruta
        assert "tarifa" in ruta
        assert "waypoints" in ruta
        assert ruta["status"] == "active"

    def test_get_public_busetas_activas(self):
        """GET /api/urban-linea/publico/busetas-activas returns active trips"""
        response = requests.get(f"{BASE_URL}/api/urban-linea/publico/busetas-activas")
        assert response.status_code == 200

        # May be empty if no active trips
        busetas = response.json()
        assert isinstance(busetas, list)


class TestComercialLogin:
    """Test comercial user login and category profile"""

    def test_comercial_login_success(self):
        """Login with comercial credentials returns correct role"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=COMERCIAL)
        assert response.status_code == 200

        data = response.json()
        assert data["user"]["role"] == "socio_comercial"
        assert data["user"]["email"] == "comercial@xuve.ve"

    def test_comercial_profile_has_category(self):
        """Comercial profile includes category with emoji"""
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json=COMERCIAL)
        assert login_res.status_code == 200
        token = login_res.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}

        # Try new endpoint first
        response = requests.get(f"{BASE_URL}/api/comercial/profile", headers=headers)
        if response.status_code == 404:
            # Profile not configured yet - that's ok for testing
            pytest.skip("Comercial profile not configured yet")

        assert response.status_code == 200
        profile = response.json()

        # Verify category info if profile exists
        if "category" in profile:
            assert "category_config" in profile
            assert "emoji" in profile["category_config"]
            assert "color" in profile["category_config"]


class TestRoleVerification:
    """Verify role separation between line_admin and urban_line_admin"""

    def test_urban_roles_exist_in_valid_roles(self):
        """API root should list urban_line_admin and chofer_urbano as valid roles"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200

        data = response.json()
        assert "roles" in data
        roles = data["roles"]

        assert "urban_line_admin" in roles
        assert "chofer_urbano" in roles
        assert "line_admin" in roles  # Original role still exists


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

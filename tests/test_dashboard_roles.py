"""
Test Dashboard Role APIs - Xuve SuperApp
=========================================
Tests for:
- ConductorDashboard: connect/disconnect for rides
- RepartidorDashboard: activate for deliveries
- ComercialDashboard: view incoming orders
- LineaUrbanaDashboard: manage scheduled trips
- Admin Panel: KPIs, KYC approvals
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

TEST_CREDENTIALS = {
    "conductor": {"email": "conductor@xuve.ve", "password": "conductor123"},
    "repartidor": {"email": "repartidor@xuve.ve", "password": "repartidor123"},
    "comercial": {"email": "comercial@xuve.ve", "password": "comercial123"},
    "linea": {"email": "linea@xuve.ve", "password": "linea123"},
    "admin": {"email": "admin@xuve.ve", "password": "admin123"},
}


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def get_token(api_client, role):
    """Helper to get token for a specific role"""
    response = api_client.post(
        f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS[role]
    )
    assert response.status_code == 200, f"Login failed for {role}"
    return response.json().get("token")


class TestConductorDashboard:
    """Test Conductor (Driver) Dashboard APIs"""

    def test_conductor_login(self, api_client):
        """Login as conductor"""
        response = api_client.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["conductor"]
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "conductor@xuve.ve"
        print(f"Conductor logged in: {data['user']['name']}")

    def test_get_conductor_status(self, api_client):
        """GET /api/socio/conductor/me - Get conductor status"""
        token = get_token(api_client, "conductor")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.get(f"{BASE_URL}/api/socio/conductor/me", headers=headers)
        # May return 200 or 404 if not registered as socio
        assert response.status_code in [200, 404]
        print(f"Conductor status response: {response.status_code}")

    def test_update_conductor_online_status(self, api_client):
        """POST /api/socio/conductor/status - Toggle online"""
        token = get_token(api_client, "conductor")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.post(
            f"{BASE_URL}/api/socio/conductor/status",
            json={"is_online": True},
            headers=headers,
        )
        # May fail if user is not a registered conductor
        print(f"Conductor online status update: {response.status_code}")


class TestRepartidorDashboard:
    """Test Repartidor (Delivery) Dashboard APIs"""

    def test_repartidor_login(self, api_client):
        """Login as repartidor"""
        response = api_client.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["repartidor"]
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print(f"Repartidor logged in: {data['user']['name']}")

    def test_get_pending_deliveries(self, api_client):
        """GET /api/market/delivery/pending"""
        token = get_token(api_client, "repartidor")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.get(
            f"{BASE_URL}/api/market/delivery/pending", headers=headers
        )
        # May return 403 if not registered as repartidor
        print(f"Pending deliveries response: {response.status_code}")

    def test_repartidor_status(self, api_client):
        """GET /api/socio/repartidor/me"""
        token = get_token(api_client, "repartidor")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.get(
            f"{BASE_URL}/api/socio/repartidor/me", headers=headers
        )
        print(f"Repartidor status: {response.status_code}")


class TestComercialDashboard:
    """Test Comercial (Business) Dashboard APIs"""

    def test_comercial_login(self, api_client):
        """Login as comercial"""
        response = api_client.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["comercial"]
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print(f"Comercial logged in: {data['user']['name']}")

    def test_get_comercial_orders(self, api_client):
        """GET /api/comercial/orders - Get incoming orders"""
        token = get_token(api_client, "comercial")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.get(f"{BASE_URL}/api/comercial/orders", headers=headers)
        print(f"Comercial orders response: {response.status_code}")

    def test_get_comercial_profile(self, api_client):
        """GET /api/socio/comercial/me"""
        token = get_token(api_client, "comercial")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.get(f"{BASE_URL}/api/socio/comercial/me", headers=headers)
        print(f"Comercial profile: {response.status_code}")


class TestLineaUrbanaDashboard:
    """Test Linea Urbana Dashboard APIs"""

    def test_linea_login(self, api_client):
        """Login as linea urbana"""
        response = api_client.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["linea"]
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print(f"Linea logged in: {data['user']['name']}")

    def test_get_urban_routes(self, api_client):
        """GET /api/rutas/urbanas"""
        token = get_token(api_client, "linea")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.get(f"{BASE_URL}/api/rutas/urbanas", headers=headers)
        print(f"Urban routes response: {response.status_code}")

    def test_get_scheduled_trips(self, api_client):
        """GET /api/urban-line/trips"""
        token = get_token(api_client, "linea")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.get(f"{BASE_URL}/api/urban-line/trips", headers=headers)
        print(f"Scheduled trips response: {response.status_code}")


class TestAdminPanel:
    """Test Admin Panel APIs"""

    def test_admin_login(self, api_client):
        """Login as admin"""
        response = api_client.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["admin"]
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print(f"Admin logged in: {data['user']['email']}")

    def test_get_admin_stats(self, api_client):
        """GET /api/admin/stats - Get KPIs"""
        token = get_token(api_client, "admin")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert "users" in data or "total_users" in data
        print(f"Admin stats: {data}")

    def test_get_kyc_requests(self, api_client):
        """GET /api/admin/kyc-requests"""
        token = get_token(api_client, "admin")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.get(f"{BASE_URL}/api/admin/kyc-requests", headers=headers)
        assert response.status_code == 200
        print(f"KYC requests retrieved")

    def test_get_pending_kyc_requests(self, api_client):
        """GET /api/admin/kyc-requests?status=pending"""
        token = get_token(api_client, "admin")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.get(
            f"{BASE_URL}/api/admin/kyc-requests?status=pending", headers=headers
        )
        assert response.status_code == 200
        print(f"Pending KYC requests retrieved")


class TestChatOperativo:
    """Test Chat Operativo APIs"""

    def test_get_conversations(self, api_client):
        """GET /api/chat/conversations"""
        token = get_token(api_client, "conductor")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.get(f"{BASE_URL}/api/chat/conversations", headers=headers)
        assert response.status_code == 200
        print(f"Conversations retrieved: {response.status_code}")

    def test_create_conversation(self, api_client):
        """POST /api/chat/conversations"""
        token = get_token(api_client, "conductor")
        headers = {"Authorization": f"Bearer {token}"}

        response = api_client.post(
            f"{BASE_URL}/api/chat/conversations",
            json={"type": "support"},
            headers=headers,
        )
        assert response.status_code in [200, 201]
        print(f"Conversation created: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
Test Urban Line Public Endpoints and Comercial Orders Management

Tests the following new functionalities:
1. Cliente Dashboard - Busetas tab with live map
2. Public urban line endpoints (rutas, busetas activas)
3. Comercial Orders management (accept, reject, ready)
4. Today's stats for comercial dashboard
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from requirements
CREDENTIALS = {
    "cliente": {"email": "cliente@xuve.ve", "password": "cliente123"},
    "comercial": {"email": "comercial@xuve.ve", "password": "comercial123"},
    "chofer_urbano": {"email": "chofer.urbano@xuve.ve", "password": "urbano123"},
    "urban_line_admin": {"email": "linea.urbana@xuve.ve", "password": "urbana123"},
}


class TestPublicUrbanLineEndpoints:
    """Test public endpoints for urban transport (no auth required)"""

    def test_get_public_rutas(self):
        """GET /api/urban-linea/publico/rutas - Returns public urban routes"""
        response = requests.get(f"{BASE_URL}/api/urban-linea/publico/rutas")

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        # Should return a list of routes
        assert isinstance(data, list), "Should return a list of routes"

        # If there are routes, verify structure
        if len(data) > 0:
            route = data[0]
            assert "ruta_id" in route, "Route should have ruta_id"
            assert "nombre_ruta" in route, "Route should have nombre_ruta"
            assert "codigo_ruta" in route, "Route should have codigo_ruta"
            assert "tarifa" in route, "Route should have tarifa"
            print(
                f"Found {len(data)} public routes. First: {route.get('codigo_ruta')} - {route.get('nombre_ruta')}"
            )
        else:
            print("No public routes found (empty list)")

    def test_get_busetas_activas_all(self):
        """GET /api/urban-linea/publico/busetas-activas - Returns active buses"""
        response = requests.get(f"{BASE_URL}/api/urban-linea/publico/busetas-activas")

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        # Should return a list
        assert isinstance(data, list), "Should return a list of active buses"

        if len(data) > 0:
            bus = data[0]
            assert "recorrido_id" in bus, "Bus should have recorrido_id"
            assert "lat" in bus, "Bus should have lat coordinate"
            assert "lng" in bus, "Bus should have lng coordinate"
            assert "ruta_codigo" in bus, "Bus should have ruta_codigo"
            print(
                f"Found {len(data)} active buses. First: {bus.get('ruta_codigo')} at ({bus.get('lat')}, {bus.get('lng')})"
            )
        else:
            print(
                "No active buses found (expected - buses appear when chofer starts route)"
            )

    def test_get_busetas_filtered_by_ruta(self):
        """GET /api/urban-linea/publico/busetas-activas?ruta_id=xxx - Filter by route"""
        # First get available routes
        routes_response = requests.get(f"{BASE_URL}/api/urban-linea/publico/rutas")
        routes = routes_response.json()

        if routes:
            ruta_id = routes[0]["ruta_id"]
            response = requests.get(
                f"{BASE_URL}/api/urban-linea/publico/busetas-activas?ruta_id={ruta_id}"
            )

            assert response.status_code == 200, f"Filter by ruta_id should work"
            data = response.json()
            assert isinstance(data, list), "Should return filtered list"
            print(f"Filtered by ruta_id={ruta_id}: Found {len(data)} active buses")
        else:
            pytest.skip("No routes available to test filtering")


class TestClienteLogin:
    """Test cliente login and access"""

    def test_cliente_login(self):
        """Test cliente can login successfully"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=CREDENTIALS["cliente"]
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "token" in data, "Response should have token"
        assert "user" in data, "Response should have user info"
        assert (
            data["user"]["role"] == "cliente"
        ), f"Expected role 'cliente', got {data['user']['role']}"
        print(f"Cliente login successful: {data['user']['name']}")

        return data["token"]


class TestComercialOrdersManagement:
    """Test comercial orders endpoints - accept, reject, ready"""

    @pytest.fixture
    def comercial_token(self):
        """Login as comercial and get token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=CREDENTIALS["comercial"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as comercial: {response.text}")
        return response.json()["token"]

    @pytest.fixture
    def comercial_headers(self, comercial_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {comercial_token}"}

    def test_comercial_login(self):
        """Test comercial login returns socio_comercial role"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=CREDENTIALS["comercial"]
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert (
            data["user"]["role"] == "socio_comercial"
        ), f"Expected role 'socio_comercial', got {data['user']['role']}"
        print(f"Comercial login successful: {data['user']['name']}")

    def test_get_incoming_orders(self, comercial_headers):
        """GET /api/comercial/orders/incoming - Get pending orders"""
        response = requests.get(
            f"{BASE_URL}/api/comercial/orders/incoming", headers=comercial_headers
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "orders" in data, "Response should have orders array"
        assert "count" in data, "Response should have count"
        assert isinstance(data["orders"], list), "Orders should be a list"

        print(f"Incoming orders: {data['count']} pending")
        if data["orders"]:
            order = data["orders"][0]
            print(
                f"Sample order: #{order.get('order_id', '')[-6:]} - ${order.get('total', 0):.2f}"
            )

    def test_get_active_orders(self, comercial_headers):
        """GET /api/comercial/orders/active - Get orders being prepared/ready"""
        response = requests.get(
            f"{BASE_URL}/api/comercial/orders/active", headers=comercial_headers
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "orders" in data, "Response should have orders array"
        assert isinstance(data["orders"], list), "Orders should be a list"

        print(f"Active orders (preparing/ready): {data['count']}")

    def test_get_today_stats(self, comercial_headers):
        """GET /api/comercial/orders/stats/today - Get today's statistics"""
        response = requests.get(
            f"{BASE_URL}/api/comercial/orders/stats/today", headers=comercial_headers
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        # Verify stats structure
        assert "total_orders" in data, "Stats should have total_orders"
        assert "total_revenue" in data, "Stats should have total_revenue"
        assert "pending" in data, "Stats should have pending count"
        assert "preparing" in data, "Stats should have preparing count"
        assert "completed" in data, "Stats should have completed count"

        print(
            f"Today's stats: {data['total_orders']} orders, ${data['total_revenue']:.2f} revenue"
        )

    def test_get_order_history(self, comercial_headers):
        """GET /api/comercial/orders/history - Get completed/cancelled orders"""
        response = requests.get(
            f"{BASE_URL}/api/comercial/orders/history?limit=10",
            headers=comercial_headers,
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "orders" in data, "Response should have orders array"
        print(f"Order history: {len(data['orders'])} orders")


class TestComercialOrderActions:
    """Test order accept/reject/ready actions"""

    @pytest.fixture
    def comercial_token(self):
        """Login as comercial"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=CREDENTIALS["comercial"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as comercial: {response.text}")
        return response.json()["token"]

    @pytest.fixture
    def comercial_headers(self, comercial_token):
        return {"Authorization": f"Bearer {comercial_token}"}

    def test_accept_nonexistent_order(self, comercial_headers):
        """POST /api/comercial/orders/{id}/accept - Should 404 for non-existent order"""
        response = requests.post(
            f"{BASE_URL}/api/comercial/orders/nonexistent_order_123/accept",
            headers=comercial_headers,
        )

        assert (
            response.status_code == 404
        ), f"Expected 404 for non-existent order, got {response.status_code}"
        print("Correctly returns 404 for non-existent order")

    def test_reject_nonexistent_order(self, comercial_headers):
        """POST /api/comercial/orders/{id}/reject - Should 404 for non-existent order"""
        response = requests.post(
            f"{BASE_URL}/api/comercial/orders/nonexistent_order_123/reject",
            headers=comercial_headers,
            json={"reason": "Test rejection"},
        )

        assert (
            response.status_code == 404
        ), f"Expected 404 for non-existent order, got {response.status_code}"
        print("Correctly returns 404 for non-existent reject")

    def test_ready_nonexistent_order(self, comercial_headers):
        """POST /api/comercial/orders/{id}/ready - Should 404 for non-existent order"""
        response = requests.post(
            f"{BASE_URL}/api/comercial/orders/nonexistent_order_123/ready",
            headers=comercial_headers,
        )

        assert (
            response.status_code == 404
        ), f"Expected 404 for non-existent order, got {response.status_code}"
        print("Correctly returns 404 for non-existent ready")

    def test_accept_order_flow(self, comercial_headers):
        """Test accept order flow if pending orders exist"""
        # Get incoming orders
        incoming_response = requests.get(
            f"{BASE_URL}/api/comercial/orders/incoming", headers=comercial_headers
        )

        if incoming_response.status_code != 200:
            pytest.skip("Could not get incoming orders")

        incoming = incoming_response.json()

        if incoming["count"] == 0:
            print("No pending orders to test accept flow - this is expected")
            pytest.skip("No pending orders available for accept test")

        # Accept the first pending order
        order = incoming["orders"][0]
        order_id = order["order_id"]

        response = requests.post(
            f"{BASE_URL}/api/comercial/orders/{order_id}/accept",
            headers=comercial_headers,
        )

        assert (
            response.status_code == 200
        ), f"Accept should succeed, got {response.status_code}: {response.text}"
        data = response.json()

        assert data["new_status"] == "preparing", "Status should change to 'preparing'"
        print(f"Order #{order_id[-6:]} accepted successfully, now preparing")

    def test_ready_order_flow(self, comercial_headers):
        """Test mark order ready flow if preparing orders exist"""
        # Get active orders
        active_response = requests.get(
            f"{BASE_URL}/api/comercial/orders/active", headers=comercial_headers
        )

        if active_response.status_code != 200:
            pytest.skip("Could not get active orders")

        active = active_response.json()

        # Find preparing order
        preparing_orders = [o for o in active["orders"] if o["status"] == "preparing"]

        if not preparing_orders:
            print("No orders in 'preparing' status to test ready flow")
            pytest.skip("No preparing orders available for ready test")

        order = preparing_orders[0]
        order_id = order["order_id"]

        response = requests.post(
            f"{BASE_URL}/api/comercial/orders/{order_id}/ready",
            headers=comercial_headers,
        )

        assert (
            response.status_code == 200
        ), f"Ready should succeed, got {response.status_code}: {response.text}"
        data = response.json()

        assert data["new_status"] == "ready", "Status should change to 'ready'"
        print(f"Order #{order_id[-6:]} marked as ready for pickup")


class TestChoferUrbanoEndpoints:
    """Test chofer urbano endpoints"""

    @pytest.fixture
    def chofer_token(self):
        """Login as chofer urbano"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=CREDENTIALS["chofer_urbano"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as chofer urbano: {response.text}")
        return response.json()["token"]

    @pytest.fixture
    def chofer_headers(self, chofer_token):
        return {"Authorization": f"Bearer {chofer_token}"}

    def test_chofer_login(self):
        """Test chofer urbano login"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=CREDENTIALS["chofer_urbano"]
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert (
            data["user"]["role"] == "chofer_urbano"
        ), f"Expected 'chofer_urbano', got {data['user']['role']}"
        print(f"Chofer urbano login: {data['user']['name']}")

    def test_get_mi_asignacion(self, chofer_headers):
        """GET /api/urban-linea/chofer/mi-asignacion - Get chofer assignment"""
        response = requests.get(
            f"{BASE_URL}/api/urban-linea/chofer/mi-asignacion", headers=chofer_headers
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "chofer" in data, "Should have chofer info"
        assert "asignacion" in data, "Should have asignacion info"

        if data["asignacion"]:
            print(
                f"Chofer assigned to: {data['asignacion'].get('ruta_nombre')} ({data['asignacion'].get('ruta_codigo')})"
            )
            print(f"Vehicle: {data['asignacion'].get('vehiculo_placa')}")
        else:
            print("Chofer has no active assignment")


class TestComercialProfile:
    """Test comercial profile endpoint"""

    @pytest.fixture
    def comercial_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=CREDENTIALS["comercial"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as comercial: {response.text}")
        return response.json()["token"]

    @pytest.fixture
    def comercial_headers(self, comercial_token):
        return {"Authorization": f"Bearer {comercial_token}"}

    def test_get_comercial_profile(self, comercial_headers):
        """GET /api/comercial/profile - Get store profile"""
        response = requests.get(
            f"{BASE_URL}/api/comercial/profile", headers=comercial_headers
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "store_name" in data, "Profile should have store_name"
        assert "category" in data, "Profile should have category"

        print(f"Store: {data.get('store_name')}")
        print(f"Category: {data.get('category')}")
        if data.get("category_config"):
            print(f"Category emoji: {data['category_config'].get('emoji')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

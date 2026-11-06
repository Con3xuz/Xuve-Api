"""
Test Market Features - Xuve SuperApp
=====================================
Tests for:
- /api/market/products (NEW endpoint)
- /api/market/stores
- /api/market/stores/{store_id}/products
- Cart functionality (via orders)
- Market orders CRUD
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
TEST_CREDENTIALS = {
    "cliente": {"email": "cliente@xuve.ve", "password": "cliente123"},
    "admin": {"email": "admin@xuve.ve", "password": "admin123"},
    "conductor": {"email": "conductor@xuve.ve", "password": "conductor123"},
    "repartidor": {"email": "repartidor@xuve.ve", "password": "repartidor123"},
    "comercial": {"email": "comercial@xuve.ve", "password": "comercial123"},
    "linea": {"email": "linea@xuve.ve", "password": "linea123"},
}


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def cliente_token(api_client):
    """Get cliente authentication token"""
    response = api_client.post(
        f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["cliente"]
    )
    assert response.status_code == 200, f"Cliente login failed: {response.text}"
    return response.json().get("token")


@pytest.fixture(scope="module")
def authenticated_client(api_client, cliente_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {cliente_token}"})
    return api_client


class TestMarketProducts:
    """Test Market Products endpoint (NEW in this session)"""

    def test_get_all_products(self, api_client):
        """GET /api/market/products - should return list of products"""
        response = api_client.get(f"{BASE_URL}/api/market/products")
        assert response.status_code == 200

        products = response.json()
        assert isinstance(products, list)
        assert len(products) > 0, "Should have at least one product"

        # Verify product structure
        product = products[0]
        assert "product_id" in product
        assert "name" in product
        assert "price_usd" in product
        assert "store_id" in product
        print(f"Found {len(products)} products")

    def test_get_products_by_store_id(self, api_client):
        """GET /api/market/products?store_id=store_001"""
        response = api_client.get(f"{BASE_URL}/api/market/products?store_id=store_001")
        assert response.status_code == 200

        products = response.json()
        assert isinstance(products, list)
        # All products should be from store_001
        for product in products:
            assert product["store_id"] == "store_001"
        print(f"Found {len(products)} products for store_001")

    def test_get_products_by_category(self, api_client):
        """GET /api/market/products?category=comida"""
        response = api_client.get(f"{BASE_URL}/api/market/products?category=comida")
        assert response.status_code == 200

        products = response.json()
        assert isinstance(products, list)
        for product in products:
            assert product["category"] == "comida"
        print(f"Found {len(products)} products in category 'comida'")


class TestMarketStores:
    """Test Market Stores endpoints"""

    def test_get_all_stores(self, api_client):
        """GET /api/market/stores"""
        response = api_client.get(f"{BASE_URL}/api/market/stores")
        assert response.status_code == 200

        stores = response.json()
        assert isinstance(stores, list)
        assert len(stores) > 0

        store = stores[0]
        assert "store_id" in store
        assert "name" in store
        assert "category" in store
        assert "is_active" in store
        print(f"Found {len(stores)} stores")

    def test_get_single_store(self, api_client):
        """GET /api/market/stores/{store_id}"""
        response = api_client.get(f"{BASE_URL}/api/market/stores/store_001")
        assert response.status_code == 200

        store = response.json()
        assert store["store_id"] == "store_001"
        assert "name" in store
        print(f"Store: {store['name']}")

    def test_get_store_products(self, api_client):
        """GET /api/market/stores/{store_id}/products"""
        response = api_client.get(f"{BASE_URL}/api/market/stores/store_001/products")
        assert response.status_code == 200

        products = response.json()
        assert isinstance(products, list)
        print(f"Store store_001 has {len(products)} products")

    def test_get_nonexistent_store(self, api_client):
        """GET /api/market/stores/{invalid_id} - should return 404"""
        response = api_client.get(f"{BASE_URL}/api/market/stores/nonexistent_store")
        assert response.status_code == 404


class TestMarketOrders:
    """Test Market Orders (Cart functionality)"""

    def test_create_market_order(self, authenticated_client):
        """POST /api/market/orders - Create order from cart items"""
        order_data = {
            "store_id": "store_001",
            "items": [
                {"product_id": "prod_001", "quantity": 2},
                {"product_id": "prod_002", "quantity": 1},
            ],
            "delivery_lat": 8.5897,
            "delivery_lng": -71.1561,
            "delivery_address": "Av. Las Américas, Mérida",
        }

        response = authenticated_client.post(
            f"{BASE_URL}/api/market/orders", json=order_data
        )
        assert response.status_code == 200

        order = response.json()
        assert "order_id" in order
        assert order["store_id"] == "store_001"
        assert order["status"] == "pending"
        assert "products_total" in order
        assert "delivery_fee" in order
        assert "total_usd" in order

        print(f"Created order: {order['order_id']}, Total: ${order['total_usd']}")
        return order["order_id"]

    def test_get_user_orders(self, authenticated_client):
        """GET /api/market/orders - Get user's orders"""
        response = authenticated_client.get(f"{BASE_URL}/api/market/orders")
        assert response.status_code == 200

        orders = response.json()
        assert isinstance(orders, list)
        print(f"User has {len(orders)} orders")


class TestAllLogins:
    """Test login for all demo roles"""

    @pytest.mark.parametrize(
        "role,creds",
        [
            ("cliente", TEST_CREDENTIALS["cliente"]),
            ("admin", TEST_CREDENTIALS["admin"]),
            ("conductor", TEST_CREDENTIALS["conductor"]),
            ("repartidor", TEST_CREDENTIALS["repartidor"]),
            ("comercial", TEST_CREDENTIALS["comercial"]),
            ("linea", TEST_CREDENTIALS["linea"]),
        ],
    )
    def test_login_all_roles(self, api_client, role, creds):
        """Test login for each role"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=creds)
        assert response.status_code == 200, f"Login failed for {role}: {response.text}"

        data = response.json()
        assert "token" in data
        assert "user" in data
        print(f"Login OK for {role}: {data['user']['email']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

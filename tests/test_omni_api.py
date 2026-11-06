"""
OMNI SuperApp Backend API Tests
Testing: Admin login, admin routes protection, driver registration role protection, market, rent, wallet
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@omni.ve"
ADMIN_PASSWORD = "admin123"


class TestAdminAuthAndRoleProtection:
    """Test admin login, role verification, and protected routes"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Seed database before tests"""
        response = requests.post(f"{BASE_URL}/api/seed")
        assert response.status_code == 200, f"Seed failed: {response.text}"

    def test_admin_login_success(self):
        """Test admin login with correct credentials returns user with role 'admin'"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"

        data = response.json()
        assert "user" in data, "Response should contain user"
        assert "token" in data, "Response should contain token"

        user = data["user"]
        assert user["email"] == ADMIN_EMAIL, f"Email mismatch: {user['email']}"
        assert (
            user["role"] == "admin"
        ), f"CRITICAL: Admin role is '{user['role']}' instead of 'admin'"
        assert user["status"] == "active", f"Admin status: {user['status']}"

        print(
            f"✅ Admin login successful - role: {user['role']}, user_id: {user['user_id']}"
        )
        return data["token"]

    def test_admin_stats_route_accessible(self):
        """Test /api/admin/stats is accessible with admin token"""
        # Login as admin
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        # Access admin stats
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)

        assert (
            response.status_code == 200
        ), f"Admin stats failed: {response.status_code} - {response.text}"

        data = response.json()
        assert "users" in data, "Response should have users count"
        assert "drivers" in data, "Response should have drivers count"
        assert "services" in data, "Response should have services count"

        print(
            f"✅ Admin stats accessible - users: {data['users']}, drivers: {data['drivers']}"
        )

    def test_admin_drivers_route_accessible(self):
        """Test /api/admin/drivers is accessible with admin token"""
        # Login as admin
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        # Access admin drivers list
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/admin/drivers", headers=headers)

        assert (
            response.status_code == 200
        ), f"Admin drivers failed: {response.status_code} - {response.text}"

        data = response.json()
        assert isinstance(data, list), "Response should be a list of drivers"

        print(f"✅ Admin drivers route accessible - found {len(data)} drivers")

    def test_admin_transactions_route_accessible(self):
        """Test /api/admin/transactions is accessible with admin token"""
        # Login as admin
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        # Access admin transactions
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/admin/transactions", headers=headers)

        assert (
            response.status_code == 200
        ), f"Admin transactions failed: {response.status_code} - {response.text}"

        data = response.json()
        assert isinstance(data, list), "Response should be a list of transactions"

        print(
            f"✅ Admin transactions route accessible - found {len(data)} transactions"
        )


class TestDriverRegistrationRoleProtection:
    """Test that driver registration does NOT change admin role"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Seed database before tests"""
        response = requests.post(f"{BASE_URL}/api/seed")
        assert response.status_code == 200

    def test_admin_role_preserved_after_driver_register(self):
        """CRITICAL TEST: Registering as driver should NOT change admin role"""
        # Step 1: Login as admin and verify role
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert login_response.status_code == 200

        admin_user = login_response.json()["user"]
        admin_token = login_response.json()["token"]
        admin_user_id = admin_user["user_id"]

        assert (
            admin_user["role"] == "admin"
        ), f"Initial admin role is '{admin_user['role']}' - should be 'admin'"
        print(f"Step 1: Admin role verified - {admin_user['role']}")

        # Step 2: Register admin as driver
        headers = {"Authorization": f"Bearer {admin_token}"}
        driver_data = {
            "user_id": admin_user_id,
            "vehicle_type": "taxi",
            "is_owner": True,
            "plate_number": f"ADM-{uuid.uuid4().hex[:4].upper()}",
            "vehicle_brand": "Toyota",
            "vehicle_model": "Corolla",
        }

        register_response = requests.post(
            f"{BASE_URL}/api/driver/register", json=driver_data, headers=headers
        )

        # Note: May return 400 if already has driver profile - that's ok
        print(f"Step 2: Driver registration response: {register_response.status_code}")

        # Step 3: Verify admin role is STILL 'admin' after registration
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_response.status_code == 200, f"Get me failed: {me_response.text}"

        updated_user = me_response.json()
        assert (
            updated_user["role"] == "admin"
        ), f"CRITICAL BUG: Admin role changed to '{updated_user['role']}' after driver registration!"

        print(
            f"✅ Step 3: Admin role preserved - still '{updated_user['role']}' after driver registration"
        )

        # Step 4: Verify admin can still access admin routes
        stats_response = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        assert (
            stats_response.status_code == 200
        ), f"Admin lost access to stats after driver registration: {stats_response.status_code}"

        print(
            f"✅ Step 4: Admin still has access to admin routes after driver registration"
        )


class TestNewUserRegistrationAndDriverRole:
    """Test normal user registration and driver registration flow"""

    def test_register_new_user_then_driver(self):
        """Register new user, then register as driver - role should become 'driver'"""
        # Create unique test user
        unique_id = uuid.uuid4().hex[:8]
        test_email = f"test_{unique_id}@test.com"

        # Step 1: Register new user
        register_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": test_email,
                "password": "testpass123",
                "name": f"Test User {unique_id}",
                "phone": "+584121234567",
            },
        )
        assert (
            register_response.status_code == 200
        ), f"User registration failed: {register_response.text}"

        data = register_response.json()
        user = data["user"]
        token = data["token"]

        assert (
            user["role"] == "user"
        ), f"New user role should be 'user', got '{user['role']}'"
        print(f"✅ Step 1: New user registered with role '{user['role']}'")

        # Step 2: Register as driver
        headers = {"Authorization": f"Bearer {token}"}
        driver_data = {
            "user_id": user["user_id"],
            "vehicle_type": "moto",
            "is_owner": True,
            "plate_number": f"TST-{unique_id[:4].upper()}",
            "vehicle_brand": "Honda",
            "vehicle_model": "Wave",
        }

        driver_response = requests.post(
            f"{BASE_URL}/api/driver/register", json=driver_data, headers=headers
        )
        assert (
            driver_response.status_code == 200
        ), f"Driver registration failed: {driver_response.text}"
        print(f"✅ Step 2: Driver registration successful")

        # Step 3: Verify role changed to 'driver'
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_response.status_code == 200

        updated_user = me_response.json()
        assert (
            updated_user["role"] == "driver"
        ), f"User role should be 'driver' after registration, got '{updated_user['role']}'"

        print(
            f"✅ Step 3: User role updated to '{updated_user['role']}' after driver registration"
        )


class TestMarketEndpoints:
    """Test OMNI Market endpoints"""

    def test_get_stores(self):
        """Test getting market stores"""
        response = requests.get(f"{BASE_URL}/api/market/stores")
        assert response.status_code == 200, f"Get stores failed: {response.text}"

        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one store (from seed)"

        store = data[0]
        assert "store_id" in store
        assert "name" in store
        assert "category" in store

        print(
            f"✅ Market stores: Found {len(data)} stores - {[s['name'] for s in data[:3]]}"
        )

    def test_get_products(self):
        """Test getting market products"""
        response = requests.get(f"{BASE_URL}/api/market/products")
        assert response.status_code == 200, f"Get products failed: {response.text}"

        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one product (from seed)"

        product = data[0]
        assert "product_id" in product
        assert "name" in product
        assert "price_usd" in product

        print(f"✅ Market products: Found {len(data)} products")

    def test_filter_stores_by_category(self):
        """Test filtering stores by category"""
        response = requests.get(f"{BASE_URL}/api/market/stores?category=comida")
        assert response.status_code == 200

        data = response.json()
        for store in data:
            assert (
                store["category"] == "comida"
            ), f"Store category mismatch: {store['category']}"

        print(f"✅ Filter stores by category: Found {len(data)} comida stores")


class TestRentEndpoints:
    """Test OMNI Rent endpoints"""

    def test_get_available_cars(self):
        """Test getting available cars for rent"""
        # Login first
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/rent/available", headers=headers)

        assert (
            response.status_code == 200
        ), f"Get available cars failed: {response.text}"

        data = response.json()
        assert isinstance(data, list), "Response should be a list"

        print(f"✅ OMNI Rent: Found {len(data)} available cars")

    def test_publish_car_for_rent(self):
        """Test publishing a car for rent"""
        # Login first
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        car_data = {
            "brand": "Ford",
            "model": "Focus",
            "year": "2019",
            "color": "Azul",
            "plateNumber": f"RNT-{uuid.uuid4().hex[:4].upper()}",
            "condition": "bueno",
            "dailyPrice": 30.0,
            "description": "Test car for rent",
            "location": "Mérida Centro",
            "photos": [],
        }

        response = requests.post(
            f"{BASE_URL}/api/rent/publish", json=car_data, headers=headers
        )

        assert response.status_code == 200, f"Publish car failed: {response.text}"

        data = response.json()
        assert "car_id" in data
        assert data["brand"] == "Ford"
        assert data["daily_price"] == 30.0

        print(f"✅ OMNI Rent: Published car with ID {data['car_id']}")


class TestWalletEndpoints:
    """Test wallet and exchange rate endpoints"""

    def test_get_wallet_balance(self):
        """Test getting wallet balance"""
        # Login first
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/wallet/balance", headers=headers)

        assert response.status_code == 200, f"Get balance failed: {response.text}"

        data = response.json()
        assert "balance" in data
        assert "currency" in data
        assert data["currency"] == "USD"

        print(f"✅ Wallet balance: ${data['balance']} {data['currency']}")

    def test_get_exchange_rate(self):
        """Test getting exchange rate"""
        response = requests.get(f"{BASE_URL}/api/exchange-rate")

        assert response.status_code == 200, f"Get exchange rate failed: {response.text}"

        data = response.json()
        assert "usd_to_bs" in data
        assert data["usd_to_bs"] > 0

        print(f"✅ Exchange rate: 1 USD = {data['usd_to_bs']} Bs")


class TestFixedRoutes:
    """Test fixed routes endpoints"""

    def test_get_routes(self):
        """Test getting fixed routes"""
        response = requests.get(f"{BASE_URL}/api/routes")

        assert response.status_code == 200, f"Get routes failed: {response.text}"

        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one route (from seed)"

        route = data[0]
        assert "route_id" in route
        assert "name" in route
        assert "fare_usd" in route

        print(
            f"✅ Fixed routes: Found {len(data)} routes - {[r['name'] for r in data]}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

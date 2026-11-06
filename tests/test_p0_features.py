"""
Xuve SuperApp P0 Features Tests - Iteration 4
==============================================
Testing:
1. Profile Page - /api/auth/me and /api/user/profile endpoints
2. Image Upload - /api/upload/image and /api/uploads/{filename}
3. Role-specific logins and dashboard access
"""

import pytest
import requests
import os
import uuid
from pathlib import Path

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials - P0 users
TEST_USERS = {
    "cliente": {"email": "cliente@xuve.ve", "password": "cliente123"},
    "comercial": {"email": "comercial@xuve.ve", "password": "comercial123"},
    "rent_owner": {"email": "rent@xuve.ve", "password": "rent123"},
    "conductor": {"email": "conductor@xuve.ve", "password": "conductor123"},
    "repartidor": {"email": "repartidor@xuve.ve", "password": "repartidor123"},
}


class TestProfileEndpoints:
    """Test profile endpoints - Bug fix verification for 'Mi Perfil' link"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Seed database before tests"""
        response = requests.get(f"{BASE_URL}/api/seed")
        assert response.status_code == 200, f"Seed failed: {response.text}"

    def test_cliente_login_and_profile(self):
        """Test cliente login and profile access - no logout issue"""
        creds = TEST_USERS["cliente"]

        # Login
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": creds["email"], "password": creds["password"]},
        )

        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        token = data["token"]
        user = data["user"]

        print(
            f"✅ Cliente login successful - user_id: {user.get('user_id')}, role: {user.get('role')}"
        )

        # Access /api/auth/me endpoint (used for profile data)
        headers = {"Authorization": f"Bearer {token}"}
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_response.status_code == 200, f"Auth/me failed: {me_response.text}"

        me_data = me_response.json()
        assert "email" in me_data, "Profile should have email"
        assert "name" in me_data, "Profile should have name"
        assert me_data["email"] == creds["email"]

        print(f"✅ Auth/me returns profile data correctly")

        # Access /api/user/profile endpoint
        profile_response = requests.get(f"{BASE_URL}/api/user/profile", headers=headers)
        assert (
            profile_response.status_code == 200
        ), f"User/profile failed: {profile_response.text}"

        profile_data = profile_response.json()
        # Verify profile contains expected fields
        expected_fields = [
            "user_id",
            "email",
            "name",
            "phone",
            "role",
            "wallet_balance",
            "kyc_status",
            "avg_rating",
        ]
        for field in expected_fields:
            assert field in profile_data, f"Profile missing field: {field}"

        print(
            f"✅ User/profile returns: name={profile_data.get('name')}, email={profile_data.get('email')}, balance={profile_data.get('wallet_balance')}"
        )

        return token

    def test_profile_update(self):
        """Test profile update via PATCH /api/auth/profile"""
        creds = TEST_USERS["cliente"]

        # Login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": creds["email"], "password": creds["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Update profile
        new_name = f"Cliente Test {uuid.uuid4().hex[:4]}"
        new_phone = "+58412-000-1234"

        update_response = requests.patch(
            f"{BASE_URL}/api/auth/profile",
            json={"name": new_name, "phone": new_phone},
            headers=headers,
        )

        assert (
            update_response.status_code == 200
        ), f"Profile update failed: {update_response.text}"
        updated = update_response.json()
        assert (
            updated.get("name") == new_name
        ), f"Name not updated: {updated.get('name')}"
        assert (
            updated.get("phone") == new_phone
        ), f"Phone not updated: {updated.get('phone')}"

        print(f"✅ Profile updated: name={new_name}, phone={new_phone}")


class TestImageUpload:
    """Test image upload endpoints"""

    def test_upload_image(self):
        """Test POST /api/upload/image with a test image"""
        # Create a small test image (1x1 pixel PNG)
        # This is a valid PNG file content
        png_header = bytes(
            [
                0x89,
                0x50,
                0x4E,
                0x47,
                0x0D,
                0x0A,
                0x1A,
                0x0A,  # PNG signature
                0x00,
                0x00,
                0x00,
                0x0D,
                0x49,
                0x48,
                0x44,
                0x52,  # IHDR chunk
                0x00,
                0x00,
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x01,  # 1x1 dimensions
                0x08,
                0x02,
                0x00,
                0x00,
                0x00,
                0x90,
                0x77,
                0x53,
                0xDE,
                0x00,
                0x00,
                0x00,
                0x0C,
                0x49,
                0x44,
                0x41,
                0x54,
                0x08,
                0xD7,
                0x63,
                0xF8,
                0xFF,
                0xFF,
                0x3F,
                0x00,
                0x05,
                0xFE,
                0x02,
                0xFE,
                0xDC,
                0xCC,
                0x59,
                0xE7,
                0x00,
                0x00,
                0x00,
                0x00,
                0x49,
                0x45,
                0x4E,
                0x44,
                0xAE,
                0x42,
                0x60,
                0x82,
            ]
        )

        files = {"file": ("test_image.png", png_header, "image/png")}

        response = requests.post(f"{BASE_URL}/api/upload/image", files=files)

        assert (
            response.status_code == 200
        ), f"Upload failed: {response.status_code} - {response.text}"

        data = response.json()
        assert "url" in data, "Response should have url"
        assert "filename" in data, "Response should have filename"
        assert data["url"].startswith(
            "/api/uploads/"
        ), f"URL format incorrect: {data['url']}"

        print(f"✅ Image uploaded successfully: {data['url']}")

        return data["url"]

    def test_serve_uploaded_file(self):
        """Test GET /api/uploads/{filename} - serve uploaded files"""
        # First upload a file
        png_header = bytes(
            [
                0x89,
                0x50,
                0x4E,
                0x47,
                0x0D,
                0x0A,
                0x1A,
                0x0A,
                0x00,
                0x00,
                0x00,
                0x0D,
                0x49,
                0x48,
                0x44,
                0x52,
                0x00,
                0x00,
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x01,
                0x08,
                0x02,
                0x00,
                0x00,
                0x00,
                0x90,
                0x77,
                0x53,
                0xDE,
                0x00,
                0x00,
                0x00,
                0x0C,
                0x49,
                0x44,
                0x41,
                0x54,
                0x08,
                0xD7,
                0x63,
                0xF8,
                0xFF,
                0xFF,
                0x3F,
                0x00,
                0x05,
                0xFE,
                0x02,
                0xFE,
                0xDC,
                0xCC,
                0x59,
                0xE7,
                0x00,
                0x00,
                0x00,
                0x00,
                0x49,
                0x45,
                0x4E,
                0x44,
                0xAE,
                0x42,
                0x60,
                0x82,
            ]
        )

        files = {"file": ("test_image.png", png_header, "image/png")}
        upload_response = requests.post(f"{BASE_URL}/api/upload/image", files=files)
        assert upload_response.status_code == 200

        file_url = upload_response.json()["url"]
        filename = upload_response.json()["filename"]

        # Fetch the uploaded file
        full_url = f"{BASE_URL}{file_url}"
        fetch_response = requests.get(full_url)

        assert (
            fetch_response.status_code == 200
        ), f"Fetch failed: {fetch_response.status_code}"
        assert "image" in fetch_response.headers.get(
            "content-type", ""
        ), "Content-type should be image"

        print(f"✅ Uploaded file served correctly: {file_url}")

    def test_upload_invalid_file_type(self):
        """Test upload rejects non-image files"""
        files = {"file": ("test.txt", b"This is a text file", "text/plain")}

        response = requests.post(f"{BASE_URL}/api/upload/image", files=files)

        assert (
            response.status_code == 400
        ), f"Should reject non-image: {response.status_code}"
        print(f"✅ Non-image file correctly rejected")


class TestRoleBasedLogins:
    """Test login for each role and verify dashboard access"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Seed database before tests"""
        response = requests.get(f"{BASE_URL}/api/seed")
        assert response.status_code == 200

    def test_conductor_login(self):
        """Test conductor login and dashboard route"""
        creds = TEST_USERS["conductor"]

        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": creds["email"], "password": creds["password"]},
        )

        assert response.status_code == 200, f"Conductor login failed: {response.text}"

        data = response.json()
        user = data["user"]
        token = data["token"]

        assert (
            user.get("role") == "socio_conductor"
        ), f"Role mismatch: {user.get('role')}"
        print(f"✅ Conductor login: {user.get('name')}, role={user.get('role')}")

        # Get dashboard route
        headers = {"Authorization": f"Bearer {token}"}
        route_response = requests.get(
            f"{BASE_URL}/api/user/dashboard-route", headers=headers
        )
        assert route_response.status_code == 200

        route_data = route_response.json()
        assert (
            route_data["dashboard_route"] == "/dashboard/conductor"
        ), f"Route: {route_data['dashboard_route']}"
        print(f"✅ Conductor dashboard route: {route_data['dashboard_route']}")

    def test_repartidor_login(self):
        """Test repartidor login and dashboard route"""
        creds = TEST_USERS["repartidor"]

        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": creds["email"], "password": creds["password"]},
        )

        assert response.status_code == 200, f"Repartidor login failed: {response.text}"

        data = response.json()
        user = data["user"]
        token = data["token"]

        assert (
            user.get("role") == "socio_repartidor"
        ), f"Role mismatch: {user.get('role')}"
        print(f"✅ Repartidor login: {user.get('name')}, role={user.get('role')}")

        # Get dashboard route
        headers = {"Authorization": f"Bearer {token}"}
        route_response = requests.get(
            f"{BASE_URL}/api/user/dashboard-route", headers=headers
        )
        assert route_response.status_code == 200

        route_data = route_response.json()
        assert (
            route_data["dashboard_route"] == "/dashboard/repartidor"
        ), f"Route: {route_data['dashboard_route']}"
        print(f"✅ Repartidor dashboard route: {route_data['dashboard_route']}")

    def test_comercial_login(self):
        """Test comercial login"""
        creds = TEST_USERS["comercial"]

        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": creds["email"], "password": creds["password"]},
        )

        assert response.status_code == 200, f"Comercial login failed: {response.text}"

        data = response.json()
        user = data["user"]
        token = data["token"]

        assert (
            user.get("role") == "socio_comercial"
        ), f"Role mismatch: {user.get('role')}"
        print(f"✅ Comercial login: {user.get('name')}, role={user.get('role')}")

        # Get dashboard route
        headers = {"Authorization": f"Bearer {token}"}
        route_response = requests.get(
            f"{BASE_URL}/api/user/dashboard-route", headers=headers
        )
        assert route_response.status_code == 200

        route_data = route_response.json()
        assert (
            route_data["dashboard_route"] == "/dashboard/comercial"
        ), f"Route: {route_data['dashboard_route']}"
        print(f"✅ Comercial dashboard route: {route_data['dashboard_route']}")

    def test_rent_owner_login(self):
        """Test rent owner login"""
        creds = TEST_USERS["rent_owner"]

        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": creds["email"], "password": creds["password"]},
        )

        assert response.status_code == 200, f"Rent owner login failed: {response.text}"

        data = response.json()
        user = data["user"]
        token = data["token"]

        assert user.get("role") == "rent_owner", f"Role mismatch: {user.get('role')}"
        print(f"✅ Rent Owner login: {user.get('name')}, role={user.get('role')}")

        # Get dashboard route
        headers = {"Authorization": f"Bearer {token}"}
        route_response = requests.get(
            f"{BASE_URL}/api/user/dashboard-route", headers=headers
        )
        assert route_response.status_code == 200

        route_data = route_response.json()
        assert (
            route_data["dashboard_route"] == "/dashboard/rent"
        ), f"Route: {route_data['dashboard_route']}"
        print(f"✅ Rent Owner dashboard route: {route_data['dashboard_route']}")


class TestComercialProfile:
    """Test comercial-specific profile endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Seed database before tests"""
        response = requests.get(f"{BASE_URL}/api/seed")
        assert response.status_code == 200

    def test_comercial_profile_endpoint(self):
        """Test /api/socio/comercial/profile endpoint"""
        creds = TEST_USERS["comercial"]

        # Login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": creds["email"], "password": creds["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}

        # Get comercial profile
        profile_response = requests.get(
            f"{BASE_URL}/api/socio/comercial/profile", headers=headers
        )

        # May return 404 if no store registered - that's expected behavior
        if profile_response.status_code == 404:
            print(
                f"✅ Comercial profile returns 404 (no store) - expected for new accounts"
            )
        else:
            assert profile_response.status_code == 200
            profile_data = profile_response.json()
            print(f"✅ Comercial profile: {profile_data.get('store_name', 'N/A')}")


class TestRentOwnerEndpoints:
    """Test rent owner specific endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Seed database before tests"""
        response = requests.get(f"{BASE_URL}/api/seed")
        assert response.status_code == 200

    def test_rent_owner_vehicles_endpoint(self):
        """Test /api/rent/owner/vehicles endpoint"""
        creds = TEST_USERS["rent_owner"]

        # Login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": creds["email"], "password": creds["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}

        # Get vehicles
        response = requests.get(f"{BASE_URL}/api/rent/owner/vehicles", headers=headers)
        assert response.status_code == 200, f"Get vehicles failed: {response.text}"

        vehicles = response.json()
        assert isinstance(vehicles, list), "Response should be a list"
        print(f"✅ Rent owner has {len(vehicles)} vehicles")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

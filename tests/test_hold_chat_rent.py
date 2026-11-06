"""
Test Suite for Xuve SuperApp - Hold, Service Chat, and Rent Features
=====================================================================
Tests the new Hold system, ServiceChat, and Rent-a-Car integration
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
CLIENTE_EMAIL = "cliente@xuve.ve"
CLIENTE_PASSWORD = "cliente123"
CONDUCTOR_EMAIL = "conductor@xuve.ve"
CONDUCTOR_PASSWORD = "conductor123"


class TestWalletHold:
    """Tests for Wallet Hold (deposit guarantee) system"""

    @pytest.fixture
    def cliente_token(self):
        """Get cliente auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENTE_EMAIL, "password": CLIENTE_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]

    def test_get_wallet_balance(self, cliente_token):
        """Test wallet balance endpoint"""
        headers = {"Authorization": f"Bearer {cliente_token}"}
        response = requests.get(f"{BASE_URL}/api/wallet/balance", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "balance" in data
        assert "currency" in data
        print(f"Balance: ${data['balance']} {data['currency']}")

    def test_get_wallet_holds(self, cliente_token):
        """Test get active holds endpoint"""
        headers = {"Authorization": f"Bearer {cliente_token}"}
        response = requests.get(f"{BASE_URL}/api/wallet/holds", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Active holds: {len(data)}")

        # Verify hold structure if any
        if len(data) > 0:
            hold = data[0]
            assert "hold_id" in hold
            assert "amount_usd" in hold
            assert "reason" in hold
            assert "status" in hold

    def test_create_hold_insufficient_funds(self, cliente_token):
        """Test creating hold with insufficient funds"""
        headers = {
            "Authorization": f"Bearer {cliente_token}",
            "Content-Type": "application/json",
        }

        # Try to create a very large hold
        response = requests.post(
            f"{BASE_URL}/api/wallet/hold",
            headers=headers,
            json={
                "amount_usd": 10000,  # Very large amount
                "reason": "rent_deposit",
                "reference_id": "test_insufficient_funds",
            },
        )

        # Should fail with insufficient funds
        assert response.status_code == 400
        assert "insuficiente" in response.json().get("detail", "").lower()
        print("Correctly rejected hold with insufficient funds")


class TestServiceChat:
    """Tests for Service Chat (Uber/Glovo style communication)"""

    @pytest.fixture
    def cliente_token(self):
        """Get cliente auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENTE_EMAIL, "password": CLIENTE_PASSWORD},
        )
        assert response.status_code == 200
        return response.json()["token"]

    @pytest.fixture
    def conductor_token(self):
        """Get conductor auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CONDUCTOR_EMAIL, "password": CONDUCTOR_PASSWORD},
        )
        assert response.status_code == 200
        return response.json()["token"]

    def test_create_service_conversation(self, cliente_token):
        """Test creating a service conversation"""
        headers = {
            "Authorization": f"Bearer {cliente_token}",
            "Content-Type": "application/json",
        }

        # Create a new service conversation for a rent service
        timestamp = int(time.time())
        response = requests.post(
            f"{BASE_URL}/api/chat/service",
            headers=headers,
            json={
                "service_type": "rent",
                "service_id": f"test_rent_{timestamp}",
                "other_user_id": "user_demo001",  # Rent owner
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        print(f"Created conversation: {data['conversation_id']}")

        return data["conversation_id"]

    def test_get_service_conversation(self, cliente_token):
        """Test getting an existing service conversation"""
        headers = {
            "Authorization": f"Bearer {cliente_token}",
            "Content-Type": "application/json",
        }

        # First create a conversation
        timestamp = int(time.time())
        service_id = f"test_rent_get_{timestamp}"

        create_response = requests.post(
            f"{BASE_URL}/api/chat/service",
            headers=headers,
            json={
                "service_type": "rent",
                "service_id": service_id,
                "other_user_id": "user_demo001",
            },
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["conversation_id"]

        # Now get the conversation
        get_response = requests.get(
            f"{BASE_URL}/api/chat/service/rent/{service_id}", headers=headers
        )

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["conversation_id"] == conv_id
        assert "messages" in data
        print(
            f"Retrieved conversation: {data['conversation_id']} with {len(data['messages'])} messages"
        )

    def test_send_message_in_service_chat(self, cliente_token):
        """Test sending a message in service chat"""
        headers = {
            "Authorization": f"Bearer {cliente_token}",
            "Content-Type": "application/json",
        }

        # Create conversation
        timestamp = int(time.time())
        service_id = f"test_rent_msg_{timestamp}"

        create_response = requests.post(
            f"{BASE_URL}/api/chat/service",
            headers=headers,
            json={
                "service_type": "rent",
                "service_id": service_id,
                "other_user_id": "user_demo001",
            },
        )
        assert create_response.status_code == 200
        conv_id = create_response.json()["conversation_id"]

        # Send a message
        msg_response = requests.post(
            f"{BASE_URL}/api/chat/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "Hola, ¿dónde nos encontramos para recoger el auto?"},
        )

        assert msg_response.status_code == 200
        msg_data = msg_response.json()
        assert "message" in msg_data
        assert (
            msg_data["message"]["content"]
            == "Hola, ¿dónde nos encontramos para recoger el auto?"
        )
        print(f"Sent message: {msg_data['message']['message_id']}")

    def test_service_conversation_not_found(self, cliente_token):
        """Test getting non-existent service conversation returns 404"""
        headers = {"Authorization": f"Bearer {cliente_token}"}

        response = requests.get(
            f"{BASE_URL}/api/chat/service/rent/nonexistent_service_xyz", headers=headers
        )

        assert response.status_code == 404
        print("Correctly returned 404 for non-existent conversation")

    def test_create_service_conversation_missing_data(self, cliente_token):
        """Test creating conversation with missing required data"""
        headers = {
            "Authorization": f"Bearer {cliente_token}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            f"{BASE_URL}/api/chat/service",
            headers=headers,
            json={
                "service_type": "rent"
                # Missing service_id and other_user_id
            },
        )

        assert response.status_code == 400
        print("Correctly rejected conversation with missing data")


class TestRentAvailable:
    """Tests for Rent-a-Car available cars endpoints"""

    @pytest.fixture
    def cliente_token(self):
        """Get cliente auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENTE_EMAIL, "password": CLIENTE_PASSWORD},
        )
        assert response.status_code == 200
        return response.json()["token"]

    def test_get_available_cars(self, cliente_token):
        """Test getting available cars - /api/rent/available"""
        headers = {"Authorization": f"Bearer {cliente_token}"}

        response = requests.get(f"{BASE_URL}/api/rent/available", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} available cars")

        # Verify car structure if any
        if len(data) > 0:
            car = data[0]
            assert "brand" in car
            assert "model" in car
            assert "daily_price" in car or "daily_rate" in car
            assert "plate_number" in car
            print(
                f"First car: {car.get('brand')} {car.get('model')} - ${car.get('daily_price', car.get('daily_rate'))}/day"
            )

    def test_get_cars_endpoint(self, cliente_token):
        """Test /api/rent/cars endpoint (original)"""
        headers = {"Authorization": f"Bearer {cliente_token}"}

        response = requests.get(f"{BASE_URL}/api/rent/cars", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} cars via /cars endpoint")

    def test_get_my_cars(self, cliente_token):
        """Test getting user's published cars"""
        headers = {"Authorization": f"Bearer {cliente_token}"}

        response = requests.get(f"{BASE_URL}/api/rent/my-cars", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"User has {len(data)} published cars")

    def test_get_my_rentals(self, cliente_token):
        """Test getting user's rental requests"""
        headers = {"Authorization": f"Bearer {cliente_token}"}

        response = requests.get(f"{BASE_URL}/api/rent/my-rentals", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"User has {len(data)} rentals")


class TestRentIntegration:
    """Tests for full Rent-a-Car workflow with Hold integration"""

    @pytest.fixture
    def cliente_token(self):
        """Get cliente auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENTE_EMAIL, "password": CLIENTE_PASSWORD},
        )
        assert response.status_code == 200
        return response.json()["token"]

    def test_rent_request_flow(self, cliente_token):
        """Test creating a rent request"""
        headers = {
            "Authorization": f"Bearer {cliente_token}",
            "Content-Type": "application/json",
        }

        # First get available cars
        cars_response = requests.get(f"{BASE_URL}/api/rent/available", headers=headers)
        assert cars_response.status_code == 200
        cars = cars_response.json()

        if len(cars) == 0:
            pytest.skip("No available cars to test rent request")

        car = cars[0]
        car_id = car.get("car_id") or car.get("vehicle_id")

        # Create rent request (without hold - just testing API)
        rent_response = requests.post(
            f"{BASE_URL}/api/rent/request", headers=headers, json={"car_id": car_id}
        )

        assert rent_response.status_code == 200
        data = rent_response.json()
        assert "message" in data
        assert "request" in data
        assert data["request"]["vehicle_id"] == car_id
        print(f"Created rent request: {data['request']['request_id']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

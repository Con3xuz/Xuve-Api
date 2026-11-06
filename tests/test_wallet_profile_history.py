"""
Test Wallet, Profile, and History Features - Xuve SuperApp
============================================================
Tests for:
- Wallet balance and exchange rates
- User profile and KYC status
- Service history
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


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
        f"{BASE_URL}/api/auth/login",
        json={"email": "cliente@xuve.ve", "password": "cliente123"},
    )
    assert response.status_code == 200
    return response.json().get("token")


@pytest.fixture(scope="module")
def authenticated_client(api_client, cliente_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {cliente_token}"})
    return api_client


class TestWallet:
    """Test Wallet endpoints"""

    def test_get_wallet_balance(self, authenticated_client):
        """GET /api/wallet/balance"""
        response = authenticated_client.get(f"{BASE_URL}/api/wallet/balance")
        assert response.status_code == 200

        data = response.json()
        assert "balance" in data or "wallet_balance" in data
        print(f"Wallet balance: {data}")

    def test_get_exchange_rate(self, api_client):
        """GET /api/exchange-rate - Get BCV exchange rate"""
        response = api_client.get(f"{BASE_URL}/api/exchange-rate")
        assert response.status_code == 200

        data = response.json()
        assert "rate" in data or "bcv_rate" in data or "usd_to_bs" in data
        print(f"Exchange rate: {data}")

    def test_get_transactions(self, authenticated_client):
        """GET /api/wallet/transactions"""
        response = authenticated_client.get(f"{BASE_URL}/api/wallet/transactions")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list) or "transactions" in data
        print(f"Transactions data retrieved")


class TestProfile:
    """Test Profile and KYC endpoints"""

    def test_get_user_profile(self, authenticated_client):
        """GET /api/user/profile - Get current user profile"""
        response = authenticated_client.get(f"{BASE_URL}/api/user/profile")
        assert response.status_code == 200

        user = response.json()
        assert "user_id" in user or "email" in user
        assert "name" in user
        print(f"Profile: {user.get('name', user.get('email'))}")

    def test_get_kyc_status(self, authenticated_client):
        """GET /api/kyc/my-status"""
        response = authenticated_client.get(f"{BASE_URL}/api/kyc/my-status")
        assert response.status_code == 200

        data = response.json()
        assert "kyc_status" in data or "status" in data
        print(f"KYC status: {data}")

    def test_get_kyc_roles_info(self, api_client):
        """GET /api/kyc/roles-info - Get available roles for KYC"""
        response = api_client.get(f"{BASE_URL}/api/kyc/roles-info")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list) or "roles" in data
        print(f"KYC roles info retrieved")


class TestHistory:
    """Test Service History endpoints"""

    def test_get_service_history(self, authenticated_client):
        """GET /api/services/history"""
        response = authenticated_client.get(f"{BASE_URL}/api/services/history")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list) or "services" in data
        print(f"Service history retrieved")

    def test_get_market_orders_history(self, authenticated_client):
        """GET /api/market/orders - User's market orders"""
        response = authenticated_client.get(f"{BASE_URL}/api/market/orders")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        print(f"Market orders: {len(data)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

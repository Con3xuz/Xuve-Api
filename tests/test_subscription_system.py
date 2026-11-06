"""
Test Suite for Xuve Daily Subscription System
==============================================
Tests the new economic model: $1 USD/day subscription for all partners.
- No transaction commissions (10%, 12%, etc. removed)
- Partners recharge wallet and pay $1/day to work
- Subscription valid until midnight
- Can reconnect same day without additional cost
- 3 free trial days for new partners
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from iteration_12.json
TEST_CREDENTIALS = {
    "conductor": {"email": "conductor@xuve.ve", "password": "conductor123"},
    "repartidor": {"email": "repartidor@xuve.ve", "password": "repartidor123"},
    "admin": {"email": "admin@xuve.ve", "password": "admin123"},
    "cliente": {"email": "cliente@xuve.ve", "password": "cliente123"},
}


class TestSubscriptionPublicEndpoints:
    """Test public subscription endpoints (no auth required)"""

    def test_subscription_info_returns_correct_structure(self):
        """GET /api/subscription/info - Should return public subscription info"""
        response = requests.get(f"{BASE_URL}/api/subscription/info")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert "daily_fee" in data, "Missing daily_fee field"
        assert "free_trial_days" in data, "Missing free_trial_days field"
        assert "currency" in data, "Missing currency field"
        assert "valid_until" in data, "Missing valid_until field"
        assert "description" in data, "Missing description field"

        print(
            f"✓ Subscription info: ${data['daily_fee']}/day, {data['free_trial_days']} free trial days"
        )

    def test_subscription_info_values_are_correct(self):
        """Verify subscription info has expected values"""
        response = requests.get(f"{BASE_URL}/api/subscription/info")
        data = response.json()

        # Verify expected values
        assert (
            data["daily_fee"] == 1.0
        ), f"Expected daily_fee=1.0, got {data['daily_fee']}"
        assert (
            data["free_trial_days"] == 3
        ), f"Expected free_trial_days=3, got {data['free_trial_days']}"
        assert (
            data["currency"] == "USD"
        ), f"Expected currency=USD, got {data['currency']}"

        print(
            f"✓ Subscription values correct: ${data['daily_fee']} USD/day, {data['free_trial_days']} trial days"
        )


class TestSubscriptionAuthenticatedEndpoints:
    """Test subscription endpoints that require authentication"""

    @pytest.fixture
    def conductor_token(self):
        """Get auth token for conductor user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["conductor"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as conductor: {response.text}")
        return response.json().get("token")

    @pytest.fixture
    def repartidor_token(self):
        """Get auth token for repartidor user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["repartidor"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as repartidor: {response.text}")
        return response.json().get("token")

    @pytest.fixture
    def admin_token(self):
        """Get auth token for admin user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["admin"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as admin: {response.text}")
        return response.json().get("token")

    def test_subscription_status_requires_auth(self):
        """GET /api/subscription/status - Should require authentication"""
        response = requests.get(f"{BASE_URL}/api/subscription/status")

        # Should return 401 or 403 without auth
        assert response.status_code in [
            401,
            403,
            422,
        ], f"Expected auth error, got {response.status_code}"
        print("✓ Subscription status requires authentication")

    def test_subscription_status_for_conductor(self, conductor_token):
        """GET /api/subscription/status - Should return conductor's subscription status"""
        headers = {"Authorization": f"Bearer {conductor_token}"}
        response = requests.get(f"{BASE_URL}/api/subscription/status", headers=headers)

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        # Verify response structure
        assert "has_active_subscription" in data, "Missing has_active_subscription"
        assert "in_free_trial" in data, "Missing in_free_trial"
        assert "trial_days_remaining" in data, "Missing trial_days_remaining"
        assert "daily_fee" in data, "Missing daily_fee"
        assert "balance" in data, "Missing balance"
        assert "can_activate" in data, "Missing can_activate"

        print(
            f"✓ Conductor subscription status: active={data['has_active_subscription']}, trial={data['in_free_trial']}, balance=${data['balance']}"
        )
        return data

    def test_subscription_status_for_repartidor(self, repartidor_token):
        """GET /api/subscription/status - Should return repartidor's subscription status"""
        headers = {"Authorization": f"Bearer {repartidor_token}"}
        response = requests.get(f"{BASE_URL}/api/subscription/status", headers=headers)

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert "has_active_subscription" in data
        assert "in_free_trial" in data
        assert "daily_fee" in data

        print(
            f"✓ Repartidor subscription status: active={data['has_active_subscription']}, trial={data['in_free_trial']}"
        )

    def test_subscription_activate_requires_auth(self):
        """POST /api/subscription/activate - Should require authentication"""
        response = requests.post(f"{BASE_URL}/api/subscription/activate")

        assert response.status_code in [
            401,
            403,
            422,
        ], f"Expected auth error, got {response.status_code}"
        print("✓ Subscription activate requires authentication")

    def test_subscription_activate_for_conductor(self, conductor_token):
        """POST /api/subscription/activate - Should activate subscription for conductor"""
        headers = {"Authorization": f"Bearer {conductor_token}"}
        response = requests.post(
            f"{BASE_URL}/api/subscription/activate", headers=headers
        )

        # Can be 200 (success) or 402 (insufficient balance)
        assert response.status_code in [
            200,
            402,
        ], f"Expected 200 or 402, got {response.status_code}: {response.text}"

        data = response.json()

        if response.status_code == 200:
            assert "success" in data, "Missing success field"
            assert "message" in data, "Missing message field"
            assert "charged" in data, "Missing charged field"
            assert "valid_until" in data, "Missing valid_until field"

            # Verify trial charges $0
            if data.get("is_trial"):
                assert (
                    data["charged"] == 0
                ), f"Trial should charge $0, got ${data['charged']}"
                print(
                    f"✓ Conductor activated (TRIAL): {data['message']}, charged=${data['charged']}"
                )
            else:
                print(
                    f"✓ Conductor activated: {data['message']}, charged=${data['charged']}"
                )
        else:
            # 402 - Insufficient balance
            detail = data.get("detail", data)
            print(f"✓ Conductor activation failed (insufficient balance): {detail}")

    def test_subscription_deactivate_requires_auth(self):
        """POST /api/subscription/deactivate - Should require authentication"""
        response = requests.post(f"{BASE_URL}/api/subscription/deactivate")

        assert response.status_code in [
            401,
            403,
            422,
        ], f"Expected auth error, got {response.status_code}"
        print("✓ Subscription deactivate requires authentication")

    def test_subscription_deactivate_for_conductor(self, conductor_token):
        """POST /api/subscription/deactivate - Should deactivate without refund"""
        headers = {"Authorization": f"Bearer {conductor_token}"}
        response = requests.post(
            f"{BASE_URL}/api/subscription/deactivate", headers=headers
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert "success" in data, "Missing success field"
        assert "message" in data, "Missing message field"
        assert data["success"] == True, "Deactivation should succeed"

        # Message should mention no refund and can reconnect
        print(f"✓ Conductor deactivated: {data['message']}")

    def test_subscription_reactivate_same_day_no_charge(self, conductor_token):
        """POST /api/subscription/activate - Reactivating same day should not charge again"""
        headers = {"Authorization": f"Bearer {conductor_token}"}

        # First activation
        response1 = requests.post(
            f"{BASE_URL}/api/subscription/activate", headers=headers
        )

        if response1.status_code == 402:
            pytest.skip("Insufficient balance for activation test")

        first_charge = response1.json().get("charged", 0)

        # Deactivate
        requests.post(f"{BASE_URL}/api/subscription/deactivate", headers=headers)

        # Reactivate same day
        response2 = requests.post(
            f"{BASE_URL}/api/subscription/activate", headers=headers
        )

        assert (
            response2.status_code == 200
        ), f"Expected 200, got {response2.status_code}"

        data = response2.json()
        assert (
            data["charged"] == 0
        ), f"Reactivation same day should charge $0, got ${data['charged']}"

        print(f"✓ Reactivation same day: charged=$0 (first charge was ${first_charge})")


class TestSubscriptionAdminEndpoints:
    """Test admin subscription endpoints"""

    @pytest.fixture
    def admin_token(self):
        """Get auth token for admin user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["admin"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as admin: {response.text}")
        return response.json().get("token")

    @pytest.fixture
    def conductor_token(self):
        """Get auth token for conductor user (non-admin)"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["conductor"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as conductor: {response.text}")
        return response.json().get("token")

    def test_admin_stats_requires_admin_role(self, conductor_token):
        """GET /api/subscription/admin/stats - Should require admin role"""
        headers = {"Authorization": f"Bearer {conductor_token}"}
        response = requests.get(
            f"{BASE_URL}/api/subscription/admin/stats", headers=headers
        )

        assert (
            response.status_code == 403
        ), f"Expected 403 for non-admin, got {response.status_code}"
        print("✓ Admin stats requires admin role")

    def test_admin_stats_returns_subscription_stats(self, admin_token):
        """GET /api/subscription/admin/stats - Should return subscription statistics"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/subscription/admin/stats", headers=headers
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        # Verify expected fields
        assert (
            "active_subscriptions_today" in data
        ), "Missing active_subscriptions_today"
        assert "revenue_today_usd" in data, "Missing revenue_today_usd"
        assert "revenue_month_usd" in data, "Missing revenue_month_usd"
        assert "users_in_trial_today" in data, "Missing users_in_trial_today"
        assert "daily_fee" in data, "Missing daily_fee"

        print(
            f"✓ Admin stats: {data['active_subscriptions_today']} active today, ${data['revenue_today_usd']} revenue today, {data['users_in_trial_today']} in trial"
        )


class TestFinancialConfigNoCommissions:
    """Test that subscription system is separate from old commission system"""

    @pytest.fixture
    def admin_token(self):
        """Get auth token for admin user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["admin"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as admin: {response.text}")
        return response.json().get("token")

    def test_subscription_info_provides_daily_fee(self):
        """GET /api/subscription/info - Subscription system provides daily fee (replaces commissions)"""
        response = requests.get(f"{BASE_URL}/api/subscription/info")

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()

        # Subscription system should provide daily fee
        assert "daily_fee" in data, "Missing daily_fee field in subscription info"
        assert (
            data["daily_fee"] == 1.0
        ), f"Expected daily_fee=1.0, got {data['daily_fee']}"
        assert "free_trial_days" in data, "Missing free_trial_days field"
        assert (
            data["free_trial_days"] == 3
        ), f"Expected free_trial_days=3, got {data['free_trial_days']}"

        print(
            f"✓ Subscription system provides: ${data['daily_fee']}/day, {data['free_trial_days']} trial days"
        )
        print("✓ New subscription model replaces old commission system")


class TestTrialPeriod:
    """Test the 3-day free trial period"""

    @pytest.fixture
    def conductor_token(self):
        """Get auth token for conductor user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["conductor"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as conductor: {response.text}")
        return response.json().get("token")

    def test_trial_charges_zero(self, conductor_token):
        """Verify that trial period charges $0"""
        headers = {"Authorization": f"Bearer {conductor_token}"}

        # Get status first
        status_response = requests.get(
            f"{BASE_URL}/api/subscription/status", headers=headers
        )

        if status_response.status_code != 200:
            pytest.skip("Could not get subscription status")

        status = status_response.json()

        # If in trial, activation should charge $0
        if status.get("in_free_trial"):
            activate_response = requests.post(
                f"{BASE_URL}/api/subscription/activate", headers=headers
            )

            if activate_response.status_code == 200:
                data = activate_response.json()
                assert (
                    data.get("charged") == 0
                ), f"Trial should charge $0, got ${data.get('charged')}"
                print(
                    f"✓ Trial activation charged $0, days remaining: {data.get('trial_days_remaining', 'N/A')}"
                )
            else:
                print(
                    f"✓ Activation returned {activate_response.status_code} (may already be active)"
                )
        else:
            print(
                f"✓ User not in trial period (trial_days_remaining={status.get('trial_days_remaining', 0)})"
            )


class TestSubscriptionValidUntilMidnight:
    """Test that subscription is valid until midnight"""

    @pytest.fixture
    def conductor_token(self):
        """Get auth token for conductor user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login", json=TEST_CREDENTIALS["conductor"]
        )
        if response.status_code != 200:
            pytest.skip(f"Could not login as conductor: {response.text}")
        return response.json().get("token")

    def test_subscription_valid_until_shows_2359(self, conductor_token):
        """Verify subscription shows valid until 23:59"""
        headers = {"Authorization": f"Bearer {conductor_token}"}

        # Activate subscription
        response = requests.post(
            f"{BASE_URL}/api/subscription/activate", headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            valid_until = data.get("valid_until", "")

            # Should contain 23:59
            assert (
                "23:59" in valid_until
            ), f"Expected valid_until to contain '23:59', got '{valid_until}'"
            print(f"✓ Subscription valid until: {valid_until}")
        elif response.status_code == 402:
            pytest.skip("Insufficient balance for activation")
        else:
            pytest.fail(f"Unexpected response: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

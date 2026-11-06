"""
Test Notification System - Xuve SuperApp
Tests for notification CRUD operations and user-specific notifications
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestNotificationSystem:
    """Notification system endpoint tests"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def login(self, email: str, password: str) -> dict:
        """Helper to login and get token"""
        response = self.session.post(
            f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("token"), data.get("user")
        return None, None

    # ==================== CLIENTE NOTIFICATIONS ====================

    def test_cliente_login_success(self):
        """Test cliente@xuve.ve can login"""
        token, user = self.login("cliente@xuve.ve", "cliente123")
        assert token is not None, "Cliente login failed"
        assert user is not None, "User data not returned"
        assert user.get("email") == "cliente@xuve.ve"
        print(f"Cliente login successful, user_id: {user.get('user_id')}")

    def test_cliente_get_notifications(self):
        """Test GET /api/notifications for cliente - should include prescription notifications"""
        token, user = self.login("cliente@xuve.ve", "cliente123")
        assert token is not None, "Login failed"

        headers = {"Authorization": f"Bearer {token}"}
        response = self.session.get(f"{BASE_URL}/api/notifications", headers=headers)

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "notifications" in data, "Response missing 'notifications' key"
        assert "unread_count" in data, "Response missing 'unread_count' key"
        assert isinstance(data["notifications"], list), "Notifications should be a list"
        assert isinstance(
            data["unread_count"], int
        ), "Unread count should be an integer"

        print(
            f"Cliente has {len(data['notifications'])} notifications, {data['unread_count']} unread"
        )

        # Check notification structure if any exist
        if data["notifications"]:
            notif = data["notifications"][0]
            assert "notification_id" in notif, "Notification missing notification_id"
            assert "type" in notif, "Notification missing type"
            assert "message" in notif, "Notification missing message"
            assert "read" in notif, "Notification missing read status"
            assert "created_at" in notif, "Notification missing created_at"
            print(
                f"First notification type: {notif.get('type')}, message: {notif.get('message')[:50]}..."
            )

    # ==================== FARMABIEN (COMERCIO) NOTIFICATIONS ====================

    def test_farmabien_login_success(self):
        """Test farmabien@xuve.ve can login"""
        token, user = self.login("farmabien@xuve.ve", "farmabien123")
        assert token is not None, "Farmabien login failed"
        assert user is not None, "User data not returned"
        assert user.get("email") == "farmabien@xuve.ve"
        assert (
            user.get("role") == "socio_comercial"
        ), f"Expected role 'socio_comercial', got {user.get('role')}"
        print(f"Farmabien login successful, role: {user.get('role')}")

    def test_farmabien_get_notifications_by_store_id(self):
        """Test GET /api/notifications for farmabien - should include store_id based notifications"""
        token, user = self.login("farmabien@xuve.ve", "farmabien123")
        assert token is not None, "Login failed"

        headers = {"Authorization": f"Bearer {token}"}
        response = self.session.get(f"{BASE_URL}/api/notifications", headers=headers)

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "notifications" in data, "Response missing 'notifications' key"
        assert "unread_count" in data, "Response missing 'unread_count' key"

        print(
            f"Farmabien has {len(data['notifications'])} notifications, {data['unread_count']} unread"
        )

        # Check for prescription_received type notifications (sent to pharmacy)
        prescription_notifs = [
            n for n in data["notifications"] if n.get("type") == "prescription_received"
        ]
        print(f"Found {len(prescription_notifs)} prescription_received notifications")

    # ==================== MEDICO NOTIFICATIONS ====================

    def test_medico_login_success(self):
        """Test medico@xuve.ve can login"""
        token, user = self.login("medico@xuve.ve", "medico123")
        assert token is not None, "Medico login failed"
        assert user is not None, "User data not returned"
        assert user.get("email") == "medico@xuve.ve"
        print(f"Medico login successful, role: {user.get('role')}")

    def test_medico_get_notifications(self):
        """Test GET /api/notifications for medico"""
        token, user = self.login("medico@xuve.ve", "medico123")
        assert token is not None, "Login failed"

        headers = {"Authorization": f"Bearer {token}"}
        response = self.session.get(f"{BASE_URL}/api/notifications", headers=headers)

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "notifications" in data
        assert "unread_count" in data
        print(
            f"Medico has {len(data['notifications'])} notifications, {data['unread_count']} unread"
        )

    # ==================== CONDUCTOR NOTIFICATIONS ====================

    def test_conductor_login_success(self):
        """Test conductor@xuve.ve can login"""
        token, user = self.login("conductor@xuve.ve", "conductor123")
        assert token is not None, "Conductor login failed"
        assert user.get("email") == "conductor@xuve.ve"
        print(f"Conductor login successful, role: {user.get('role')}")

    def test_conductor_get_notifications(self):
        """Test GET /api/notifications for conductor"""
        token, user = self.login("conductor@xuve.ve", "conductor123")
        assert token is not None, "Login failed"

        headers = {"Authorization": f"Bearer {token}"}
        response = self.session.get(f"{BASE_URL}/api/notifications", headers=headers)

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "notifications" in data
        assert "unread_count" in data
        print(
            f"Conductor has {len(data['notifications'])} notifications, {data['unread_count']} unread"
        )

    # ==================== REPARTIDOR NOTIFICATIONS ====================

    def test_repartidor_login_success(self):
        """Test repartidor@xuve.ve can login"""
        token, user = self.login("repartidor@xuve.ve", "repartidor123")
        assert token is not None, "Repartidor login failed"
        assert user.get("email") == "repartidor@xuve.ve"
        print(f"Repartidor login successful, role: {user.get('role')}")

    def test_repartidor_get_notifications(self):
        """Test GET /api/notifications for repartidor"""
        token, user = self.login("repartidor@xuve.ve", "repartidor123")
        assert token is not None, "Login failed"

        headers = {"Authorization": f"Bearer {token}"}
        response = self.session.get(f"{BASE_URL}/api/notifications", headers=headers)

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "notifications" in data
        assert "unread_count" in data
        print(
            f"Repartidor has {len(data['notifications'])} notifications, {data['unread_count']} unread"
        )

    # ==================== COMERCIAL NOTIFICATIONS ====================

    def test_comercial_login_success(self):
        """Test comercial@xuve.ve can login"""
        token, user = self.login("comercial@xuve.ve", "comercial123")
        assert token is not None, "Comercial login failed"
        assert user.get("email") == "comercial@xuve.ve"
        print(f"Comercial login successful, role: {user.get('role')}")

    def test_comercial_get_notifications(self):
        """Test GET /api/notifications for comercial"""
        token, user = self.login("comercial@xuve.ve", "comercial123")
        assert token is not None, "Login failed"

        headers = {"Authorization": f"Bearer {token}"}
        response = self.session.get(f"{BASE_URL}/api/notifications", headers=headers)

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert "notifications" in data
        assert "unread_count" in data
        print(
            f"Comercial has {len(data['notifications'])} notifications, {data['unread_count']} unread"
        )

    # ==================== MARK AS READ TESTS ====================

    def test_mark_notification_as_read(self):
        """Test POST /api/notifications/{id}/read"""
        token, user = self.login("cliente@xuve.ve", "cliente123")
        assert token is not None, "Login failed"

        headers = {"Authorization": f"Bearer {token}"}

        # First get notifications
        response = self.session.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()

        if not data["notifications"]:
            pytest.skip("No notifications to mark as read")

        # Find an unread notification
        unread = [n for n in data["notifications"] if not n.get("read")]
        if not unread:
            pytest.skip("No unread notifications to test")

        notif_id = unread[0]["notification_id"]

        # Mark as read
        response = self.session.post(
            f"{BASE_URL}/api/notifications/{notif_id}/read", headers=headers
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        result = response.json()
        assert "message" in result
        print(f"Marked notification {notif_id} as read: {result['message']}")

        # Verify it's now read
        response = self.session.get(f"{BASE_URL}/api/notifications", headers=headers)
        data = response.json()
        marked_notif = next(
            (n for n in data["notifications"] if n["notification_id"] == notif_id), None
        )
        if marked_notif:
            assert marked_notif["read"] == True, "Notification should be marked as read"

    def test_mark_all_notifications_as_read(self):
        """Test POST /api/notifications/read-all"""
        token, user = self.login("cliente@xuve.ve", "cliente123")
        assert token is not None, "Login failed"

        headers = {"Authorization": f"Bearer {token}"}

        # Mark all as read
        response = self.session.post(
            f"{BASE_URL}/api/notifications/read-all", headers=headers
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        result = response.json()
        assert "message" in result
        print(f"Mark all read result: {result['message']}")

        # Verify unread count is 0
        response = self.session.get(f"{BASE_URL}/api/notifications", headers=headers)
        data = response.json()
        assert (
            data["unread_count"] == 0
        ), f"Expected 0 unread, got {data['unread_count']}"

    # ==================== DELETE NOTIFICATION TEST ====================

    def test_delete_notification(self):
        """Test DELETE /api/notifications/{id}"""
        token, user = self.login("cliente@xuve.ve", "cliente123")
        assert token is not None, "Login failed"

        headers = {"Authorization": f"Bearer {token}"}

        # First get notifications
        response = self.session.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()

        if not data["notifications"]:
            pytest.skip("No notifications to delete")

        notif_id = data["notifications"][0]["notification_id"]
        initial_count = len(data["notifications"])

        # Delete notification
        response = self.session.delete(
            f"{BASE_URL}/api/notifications/{notif_id}", headers=headers
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        result = response.json()
        assert "message" in result
        print(f"Deleted notification {notif_id}: {result['message']}")

        # Verify it's deleted
        response = self.session.get(f"{BASE_URL}/api/notifications", headers=headers)
        data = response.json()
        assert (
            len(data["notifications"]) == initial_count - 1
        ), "Notification count should decrease by 1"
        deleted_notif = next(
            (n for n in data["notifications"] if n["notification_id"] == notif_id), None
        )
        assert deleted_notif is None, "Deleted notification should not exist"

    # ==================== ERROR CASES ====================

    def test_mark_nonexistent_notification_as_read(self):
        """Test marking non-existent notification returns 404"""
        token, user = self.login("cliente@xuve.ve", "cliente123")
        assert token is not None, "Login failed"

        headers = {"Authorization": f"Bearer {token}"}

        response = self.session.post(
            f"{BASE_URL}/api/notifications/nonexistent_id/read", headers=headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_delete_nonexistent_notification(self):
        """Test deleting non-existent notification returns 404"""
        token, user = self.login("cliente@xuve.ve", "cliente123")
        assert token is not None, "Login failed"

        headers = {"Authorization": f"Bearer {token}"}

        response = self.session.delete(
            f"{BASE_URL}/api/notifications/nonexistent_id", headers=headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_notifications_require_auth(self):
        """Test that notifications endpoint requires authentication"""
        response = self.session.get(f"{BASE_URL}/api/notifications")
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

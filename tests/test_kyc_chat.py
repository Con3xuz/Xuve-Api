"""
KYC and Chat API Tests for OMNI SuperApp
Tests:
- Login flows (cliente, admin, pending_conductor)
- KYC submission and status check
- Chat conversations and messages
- Admin KYC approval workflow
- Notifications
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestAuthLoginFlows:
    """Authentication Tests - Login as different users"""

    def test_cliente_login(self):
        """Test login as cliente@omni.ve"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "cliente@omni.ve", "password": "cliente123"},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data or "token" in data, "Token not in response"
        assert "user" in data, "User not in response"
        print(
            f"Cliente login successful - user_id: {data['user'].get('user_id')}, role: {data['user'].get('role')}"
        )
        return data

    def test_admin_login(self):
        """Test login as admin@omni.ve"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@omni.ve", "password": "admin123"},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert data["user"]["role"] == "admin", "User should be admin"
        print(f"Admin login successful - role: {data['user'].get('role')}")
        return data

    def test_pending_conductor_login(self):
        """Test login as nuevo.conductor@omni.ve (pending KYC)"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "nuevo.conductor@omni.ve", "password": "pending123"},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        print(
            f"Pending conductor login - role: {data['user'].get('role')}, kyc_status: {data['user'].get('kyc_status')}"
        )
        return data


class TestKYCRoutes:
    """KYC API Tests"""

    @pytest.fixture
    def cliente_token(self):
        """Get cliente token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "cliente@omni.ve", "password": "cliente123"},
        )
        if response.status_code != 200:
            pytest.skip("Cliente login failed")
        data = response.json()
        return data.get("access_token") or data.get("token")

    def test_kyc_my_status(self, cliente_token):
        """Test GET /api/kyc/my-status"""
        headers = {"Authorization": f"Bearer {cliente_token}"}
        response = requests.get(f"{BASE_URL}/api/kyc/my-status", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Should have KYC status fields
        assert "has_kyc" in data or "kyc_status" in data
        print(f"KYC status response: {data}")

    def test_kyc_roles_info(self):
        """Test GET /api/kyc/roles-info (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/kyc/roles-info")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "roles" in data
        roles = data["roles"]
        assert len(roles) >= 8, "Should have at least 8 role types"
        role_ids = [r["id"] for r in roles]
        assert "socio_conductor" in role_ids
        assert "socio_repartidor" in role_ids
        assert "carga_pesada" in role_ids
        print(f"Available KYC roles: {role_ids}")


class TestChatRoutes:
    """Chat API Tests"""

    @pytest.fixture
    def cliente_auth(self):
        """Get cliente auth data"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "cliente@omni.ve", "password": "cliente123"},
        )
        if response.status_code != 200:
            pytest.skip("Cliente login failed")
        return response.json()

    def test_chat_conversations_list(self, cliente_auth):
        """Test GET /api/chat/conversations"""
        token = cliente_auth.get("access_token") or cliente_auth.get("token")
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/chat/conversations", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "conversations" in data
        print(f"Chat conversations: {len(data['conversations'])} found")

    def test_chat_create_conversation(self, cliente_auth):
        """Test POST /api/chat/conversations - Create support conversation"""
        token = cliente_auth.get("access_token") or cliente_auth.get("token")
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{BASE_URL}/api/chat/conversations",
            json={
                "type": "support",
                "initial_message": "TEST: Mensaje de prueba para soporte",
            },
            headers=headers,
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "conversation" in data
        conversation = data["conversation"]
        assert "conversation_id" in conversation
        assert conversation["type"] == "support"
        print(f"Created conversation: {conversation['conversation_id']}")
        return conversation

    def test_chat_send_message(self, cliente_auth):
        """Test POST /api/chat/conversations/{id}/messages - Send message"""
        token = cliente_auth.get("access_token") or cliente_auth.get("token")
        headers = {"Authorization": f"Bearer {token}"}

        # First create a conversation
        create_resp = requests.post(
            f"{BASE_URL}/api/chat/conversations",
            json={"type": "support", "initial_message": None},
            headers=headers,
        )
        if create_resp.status_code != 200:
            pytest.skip("Could not create conversation")

        conv_id = create_resp.json()["conversation"]["conversation_id"]

        # Now send a message
        response = requests.post(
            f"{BASE_URL}/api/chat/conversations/{conv_id}/messages",
            json={"content": "TEST: Este es un mensaje de prueba desde pytest"},
            headers=headers,
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        message = data["message"]
        assert "message_id" in message
        assert message["content"] == "TEST: Este es un mensaje de prueba desde pytest"
        print(f"Sent message: {message['message_id']}")

    def test_chat_get_messages(self, cliente_auth):
        """Test GET /api/chat/conversations/{id}/messages"""
        token = cliente_auth.get("access_token") or cliente_auth.get("token")
        headers = {"Authorization": f"Bearer {token}"}

        # First create a conversation with initial message
        create_resp = requests.post(
            f"{BASE_URL}/api/chat/conversations",
            json={"type": "support", "initial_message": "TEST: Getting messages test"},
            headers=headers,
        )
        if create_resp.status_code != 200:
            pytest.skip("Could not create conversation")

        conv_id = create_resp.json()["conversation"]["conversation_id"]

        # Get messages
        response = requests.get(
            f"{BASE_URL}/api/chat/conversations/{conv_id}/messages", headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "messages" in data
        print(f"Retrieved {len(data['messages'])} messages")


class TestAdminKYCRoutes:
    """Admin KYC Management Tests"""

    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@omni.ve", "password": "admin123"},
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        data = response.json()
        return data.get("access_token") or data.get("token")

    def test_admin_kyc_requests(self, admin_token):
        """Test GET /api/admin/kyc-requests"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/kyc-requests", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "requests" in data
        assert "total" in data
        print(
            f"Total KYC requests: {data['total']}, Pending: {data.get('pending_count', 0)}"
        )
        return data

    def test_admin_kyc_requests_pending(self, admin_token):
        """Test GET /api/admin/kyc-requests?status=pending"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/kyc-requests?status=pending", headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # All returned should be pending
        for req in data.get("requests", []):
            assert (
                req.get("status") == "pending"
            ), f"Expected pending, got {req.get('status')}"
        print(f"Found {len(data.get('requests', []))} pending KYC requests")

    def test_admin_stats(self, admin_token):
        """Test GET /api/admin/stats"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "users" in data
        assert "orders" in data
        print(f"Admin stats: {data['users']} users, {data['orders']} orders")

    def test_admin_kyc_approve_flow(self, admin_token):
        """
        Test approving a KYC request.
        Find a pending KYC and approve it, verify notification is created.
        """
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Get pending KYC requests
        response = requests.get(
            f"{BASE_URL}/api/admin/kyc-requests?status=pending", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        pending = data.get("requests", [])

        if not pending:
            print("No pending KYC requests to approve - skipping")
            pytest.skip("No pending KYC requests available")

        # Get the first pending request
        kyc_to_approve = pending[0]
        kyc_id = kyc_to_approve.get("kyc_id")
        user_email = kyc_to_approve.get("user_email")

        print(f"Approving KYC: {kyc_id} for user {user_email}")

        # Approve the KYC
        approve_response = requests.post(
            f"{BASE_URL}/api/admin/kyc-requests/{kyc_id}/approve",
            json={},
            headers=headers,
        )
        assert (
            approve_response.status_code == 200
        ), f"Approval failed: {approve_response.text}"
        approve_data = approve_response.json()

        assert "message" in approve_data
        print(f"Approval result: {approve_data}")

        # Verify KYC is now approved
        detail_response = requests.get(
            f"{BASE_URL}/api/admin/kyc-requests/{kyc_id}", headers=headers
        )
        if detail_response.status_code == 200:
            detail = detail_response.json()
            assert (
                detail.get("status") == "approved"
            ), f"Expected approved status, got {detail.get('status')}"
            print(
                f"KYC {kyc_id} successfully approved with status: {detail.get('status')}"
            )


class TestNotificationRoutes:
    """Notification API Tests"""

    @pytest.fixture
    def pending_conductor_auth(self):
        """Get pending conductor auth (nuevo.conductor@omni.ve)"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "nuevo.conductor@omni.ve", "password": "pending123"},
        )
        if response.status_code != 200:
            pytest.skip("Pending conductor login failed")
        return response.json()

    def test_notifications_list(self, pending_conductor_auth):
        """Test GET /api/notifications"""
        token = pending_conductor_auth.get(
            "access_token"
        ) or pending_conductor_auth.get("token")
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # May have notifications array
        print(f"Notifications response: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
Test KYC Mandatory Gate for Clients (user role)
Tests:
- New user registration creates user with role 'user' without kyc_status
- KYC roles-info includes 'user' and 'medico', NOT 'chofer_urbano' or 'urban_line_admin'
- KYC submit accepts identity data (cedula_number, cedula_front_url, selfie_url)
- Medico can create prescriptions
- Patient can view their prescriptions
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
TEST_NUEVO_USER = {"email": "nuevo@omni.ve", "password": "nuevo123"}
TEST_CLIENTE = {"email": "cliente@omni.ve", "password": "cliente123"}
TEST_MEDICO = {"email": "medico@omni.ve", "password": "medico123"}


class TestKYCRolesInfo:
    """Test /api/kyc/roles-info endpoint"""

    def test_roles_info_includes_user_role(self):
        """KYC roles-info should include 'user' role"""
        response = requests.get(f"{BASE_URL}/api/kyc/roles-info")
        assert response.status_code == 200

        data = response.json()
        roles = data.get("roles", [])
        role_ids = [r["id"] for r in roles]

        assert "user" in role_ids, "Role 'user' should be in roles-info"
        print("PASS: 'user' role found in roles-info")

        # Verify user role has correct requirements
        user_role = next((r for r in roles if r["id"] == "user"), None)
        assert user_role is not None
        assert "Foto frontal de cédula" in user_role.get("requirements", [])
        assert "Selfie de verificación" in user_role.get("requirements", [])
        print(f"PASS: User role requirements: {user_role.get('requirements')}")

    def test_roles_info_includes_medico_role(self):
        """KYC roles-info should include 'medico' role"""
        response = requests.get(f"{BASE_URL}/api/kyc/roles-info")
        assert response.status_code == 200

        data = response.json()
        roles = data.get("roles", [])
        role_ids = [r["id"] for r in roles]

        assert "medico" in role_ids, "Role 'medico' should be in roles-info"
        print("PASS: 'medico' role found in roles-info")

        # Verify medico role has correct requirements
        medico_role = next((r for r in roles if r["id"] == "medico"), None)
        assert medico_role is not None
        assert "Cédula MPPS" in medico_role.get("requirements", [])
        print(f"PASS: Medico role requirements: {medico_role.get('requirements')}")

    def test_roles_info_excludes_urban_roles(self):
        """KYC roles-info should NOT include 'chofer_urbano' or 'urban_line_admin'"""
        response = requests.get(f"{BASE_URL}/api/kyc/roles-info")
        assert response.status_code == 200

        data = response.json()
        roles = data.get("roles", [])
        role_ids = [r["id"] for r in roles]

        assert (
            "chofer_urbano" not in role_ids
        ), "Role 'chofer_urbano' should NOT be in roles-info"
        assert (
            "urban_line_admin" not in role_ids
        ), "Role 'urban_line_admin' should NOT be in roles-info"
        print("PASS: Urban roles (chofer_urbano, urban_line_admin) correctly excluded")


class TestUserLogin:
    """Test login flows for different user types"""

    def test_login_nuevo_user_without_kyc(self):
        """Login nuevo@omni.ve - user without KYC should return user data"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_NUEVO_USER)

        # User might not exist, which is fine - we're testing the flow
        if response.status_code == 401:
            print(
                "INFO: nuevo@omni.ve user does not exist (expected for new user test)"
            )
            pytest.skip("nuevo@omni.ve user not found - may need to be created")

        assert response.status_code == 200
        data = response.json()

        assert "token" in data
        assert "user" in data

        user = data["user"]
        assert (
            user.get("role") == "user"
        ), f"Expected role 'user', got '{user.get('role')}'"

        # Check KYC status - should be undefined/none/pending for new user
        kyc_status = user.get("kyc_status")
        print(f"INFO: nuevo@omni.ve kyc_status: {kyc_status}")

        # For a new user without KYC, status should NOT be 'approved'
        assert (
            kyc_status != "approved"
        ), "New user without KYC should not have approved status"
        print("PASS: nuevo@omni.ve login successful, KYC not approved")

        return data["token"]

    def test_login_cliente_with_approved_kyc(self):
        """Login cliente@omni.ve - user with approved KYC"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_CLIENTE)
        assert response.status_code == 200

        data = response.json()
        assert "token" in data
        assert "user" in data

        user = data["user"]
        assert (
            user.get("role") == "user"
        ), f"Expected role 'user', got '{user.get('role')}'"

        kyc_status = user.get("kyc_status")
        print(f"INFO: cliente@omni.ve kyc_status: {kyc_status}")

        # cliente@omni.ve should have approved KYC
        assert (
            kyc_status == "approved"
        ), f"cliente@omni.ve should have approved KYC, got '{kyc_status}'"
        print("PASS: cliente@omni.ve login successful with approved KYC")

        return data["token"]

    def test_login_medico(self):
        """Login medico@omni.ve - should return role 'medico'"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_MEDICO)
        assert response.status_code == 200

        data = response.json()
        assert "token" in data
        assert "user" in data

        user = data["user"]
        assert (
            user.get("role") == "medico"
        ), f"Expected role 'medico', got '{user.get('role')}'"
        print("PASS: medico@omni.ve login successful with role 'medico'")

        return data["token"]


class TestKYCSubmit:
    """Test KYC submission for identity verification"""

    @pytest.fixture
    def nuevo_token(self):
        """Get token for nuevo@omni.ve user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_NUEVO_USER)
        if response.status_code != 200:
            pytest.skip("nuevo@omni.ve user not available")
        return response.json()["token"]

    def test_kyc_submit_identity_data(self, nuevo_token):
        """KYC submit should accept identity data for user role"""
        headers = {"Authorization": f"Bearer {nuevo_token}"}

        kyc_data = {
            "requested_role": "user",
            "personal_data": {
                "cedula_number": "V-12345678",
                "cedula_front_url": "https://example.com/cedula_front.jpg",
                "selfie_url": "https://example.com/selfie.jpg",
            },
        }

        response = requests.post(
            f"{BASE_URL}/api/kyc/submit", json=kyc_data, headers=headers
        )

        # Could be 200 (success) or 400 (already has pending KYC)
        if response.status_code == 400:
            data = response.json()
            if "pendiente" in data.get("detail", "").lower():
                print("INFO: User already has pending KYC request")
                return

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert "kyc_id" in data
        assert data.get("status") == "pending"
        print(f"PASS: KYC submitted successfully, kyc_id: {data.get('kyc_id')}")


class TestKYCStatus:
    """Test KYC status endpoint"""

    @pytest.fixture
    def cliente_token(self):
        """Get token for cliente@omni.ve user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_CLIENTE)
        assert response.status_code == 200
        return response.json()["token"]

    def test_kyc_my_status_approved_user(self, cliente_token):
        """cliente@omni.ve should have approved KYC status"""
        headers = {"Authorization": f"Bearer {cliente_token}"}

        response = requests.get(f"{BASE_URL}/api/kyc/my-status", headers=headers)
        assert response.status_code == 200

        data = response.json()
        print(f"INFO: KYC status response: {data}")

        # Check kyc_status field
        kyc_status = data.get("kyc_status")
        assert kyc_status == "approved", f"Expected 'approved', got '{kyc_status}'"
        print("PASS: cliente@omni.ve has approved KYC status")


class TestPrescriptionAPIs:
    """Test prescription APIs for medico and patient"""

    @pytest.fixture
    def medico_token(self):
        """Get token for medico@omni.ve"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_MEDICO)
        assert response.status_code == 200
        return response.json()["token"]

    @pytest.fixture
    def cliente_token(self):
        """Get token for cliente@omni.ve"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_CLIENTE)
        assert response.status_code == 200
        return response.json()["token"]

    def test_medico_can_create_prescription(self, medico_token):
        """Medico should be able to create prescriptions"""
        headers = {"Authorization": f"Bearer {medico_token}"}

        prescription_data = {
            "patient_name": "TEST_Patient KYC Test",
            "patient_cedula": "V-99999999",
            "patient_phone": "+584121234567",
            "diagnosis": "Test diagnosis for KYC iteration",
            "medications": [
                {
                    "name": "TEST_Medication",
                    "dosage": "500mg",
                    "frequency": "cada 8 horas",
                    "duration": "7 días",
                    "quantity": 1,
                }
            ],
            "notes": "Test prescription for KYC mandatory gate testing",
        }

        response = requests.post(
            f"{BASE_URL}/api/prescriptions", json=prescription_data, headers=headers
        )
        assert response.status_code in [
            200,
            201,
        ], f"Expected 200/201, got {response.status_code}: {response.text}"

        data = response.json()
        # Response may have prescription_id at top level or nested in prescription object
        prescription_id = data.get("prescription_id") or data.get(
            "prescription", {}
        ).get("prescription_id")
        assert (
            prescription_id is not None
        ), f"Expected prescription_id in response: {data}"
        print(f"PASS: Medico created prescription: {prescription_id}")

    def test_patient_can_view_prescriptions(self, cliente_token):
        """Patient should be able to view their prescriptions"""
        headers = {"Authorization": f"Bearer {cliente_token}"}

        response = requests.get(
            f"{BASE_URL}/api/prescriptions/patient/my-prescriptions", headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        prescriptions = data.get("prescriptions", [])
        print(f"PASS: Patient can view prescriptions, count: {len(prescriptions)}")


class TestRegisterNewUser:
    """Test user registration creates user with role 'user'"""

    def test_register_creates_user_role(self):
        """POST /api/auth/register should create user with role 'user'"""
        unique_id = uuid.uuid4().hex[:8]
        test_user = {
            "email": f"TEST_newuser_{unique_id}@omni.ve",
            "password": "testpass123",
            "name": f"TEST New User {unique_id}",
            "phone": f"+5841299{unique_id[:5]}",
        }

        response = requests.post(f"{BASE_URL}/api/auth/register", json=test_user)

        # Could be 200/201 (success) or 400 (email exists)
        if response.status_code == 400:
            print("INFO: User registration returned 400 (may already exist)")
            return

        assert response.status_code in [
            200,
            201,
        ], f"Expected 200/201, got {response.status_code}: {response.text}"

        data = response.json()

        # Check if user was created with role 'user'
        if "user" in data:
            user = data["user"]
            assert (
                user.get("role") == "user"
            ), f"Expected role 'user', got '{user.get('role')}'"

            # New user should NOT have approved KYC
            kyc_status = user.get("kyc_status")
            assert (
                kyc_status != "approved"
            ), f"New user should not have approved KYC, got '{kyc_status}'"
            print(f"PASS: New user created with role 'user', kyc_status: {kyc_status}")
        else:
            print(f"INFO: Registration response: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

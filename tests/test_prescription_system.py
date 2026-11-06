"""
OMNI - Prescription System Tests
================================
Tests for the new medical prescription system:
- Medico role login and dashboard
- Prescription CRUD operations
- Patient prescription viewing
- Pharmacy prescription management
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
MEDICO_EMAIL = "medico@omni.ve"
MEDICO_PASSWORD = "medico123"
CLIENTE_EMAIL = "cliente@omni.ve"
CLIENTE_PASSWORD = "cliente123"
FARMABIEN_EMAIL = "farmabien@omni.ve"
FARMABIEN_PASSWORD = "farmabien123"
COMERCIAL_EMAIL = "comercial@omni.ve"
COMERCIAL_PASSWORD = "comercial123"


class TestMedicoLogin:
    """Test medico role authentication"""

    def test_medico_login_returns_medico_role(self):
        """Login as medico@omni.ve should return role 'medico'"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": MEDICO_EMAIL, "password": MEDICO_PASSWORD},
        )

        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()

        assert "user" in data, "Response should contain user object"
        assert "token" in data, "Response should contain token"
        assert (
            data["user"]["role"] == "medico"
        ), f"Expected role 'medico', got '{data['user']['role']}'"
        assert data["user"]["email"] == MEDICO_EMAIL
        print(f"✓ Medico login successful - role: {data['user']['role']}")

    def test_farmabien_login_returns_socio_comercial(self):
        """Login as farmabien@omni.ve should return role 'socio_comercial'"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": FARMABIEN_EMAIL, "password": FARMABIEN_PASSWORD},
        )

        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()

        assert (
            data["user"]["role"] == "socio_comercial"
        ), f"Expected role 'socio_comercial', got '{data['user']['role']}'"
        print(f"✓ Farmabien login successful - role: {data['user']['role']}")


class TestPrescriptionCreation:
    """Test prescription creation by medico"""

    @pytest.fixture
    def medico_token(self):
        """Get medico auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": MEDICO_EMAIL, "password": MEDICO_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Medico login failed")
        return response.json()["token"]

    @pytest.fixture
    def cliente_token(self):
        """Get cliente auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENTE_EMAIL, "password": CLIENTE_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Cliente login failed")
        return response.json()["token"]

    def test_create_prescription_requires_medico_role(self, cliente_token):
        """Non-medico users cannot create prescriptions"""
        headers = {"Authorization": f"Bearer {cliente_token}"}
        response = requests.post(
            f"{BASE_URL}/api/prescriptions",
            json={
                "patient_name": "Test Patient",
                "patient_cedula": "V-12345678",
                "medications": [{"name": "Test Med", "dosage": "100mg"}],
            },
            headers=headers,
        )

        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Non-medico users cannot create prescriptions")

    def test_create_prescription_success(self, medico_token):
        """Medico can create a prescription"""
        headers = {"Authorization": f"Bearer {medico_token}"}

        prescription_data = {
            "patient_name": "TEST_Juan Pérez",
            "patient_cedula": "V-99999999",
            "patient_phone": "+58412999999",
            "diagnosis": "TEST_Gripe común",
            "medications": [
                {
                    "name": "Acetaminofén",
                    "dosage": "500mg",
                    "frequency": "cada 8 horas",
                    "duration": "5 días",
                    "quantity": 15,
                    "notes": "Tomar con alimentos",
                }
            ],
            "notes": "Reposo por 3 días",
        }

        response = requests.post(
            f"{BASE_URL}/api/prescriptions", json=prescription_data, headers=headers
        )

        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()

        assert "prescription" in data, "Response should contain prescription"
        rx = data["prescription"]
        assert rx["patient_name"] == "TEST_Juan Pérez"
        assert rx["patient_cedula"] == "V-99999999"
        assert rx["status"] == "created"
        assert len(rx["medications"]) == 1
        assert rx["medications"][0]["name"] == "Acetaminofén"
        assert "prescription_id" in rx

        print(f"✓ Prescription created: {rx['prescription_id']}")
        return rx["prescription_id"]


class TestMedicoPrescriptionList:
    """Test medico viewing their prescriptions"""

    @pytest.fixture
    def medico_token(self):
        """Get medico auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": MEDICO_EMAIL, "password": MEDICO_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Medico login failed")
        return response.json()["token"]

    def test_get_my_prescriptions(self, medico_token):
        """Medico can view their issued prescriptions"""
        headers = {"Authorization": f"Bearer {medico_token}"}
        response = requests.get(
            f"{BASE_URL}/api/prescriptions/my-prescriptions", headers=headers
        )

        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()

        assert "prescriptions" in data, "Response should contain prescriptions list"
        assert "pagination" in data, "Response should contain pagination"
        assert isinstance(data["prescriptions"], list)

        print(f"✓ Medico has {len(data['prescriptions'])} prescriptions")

    def test_get_medico_stats(self, medico_token):
        """Medico can view their stats"""
        headers = {"Authorization": f"Bearer {medico_token}"}
        response = requests.get(f"{BASE_URL}/api/prescriptions/stats", headers=headers)

        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()

        assert "total_prescriptions" in data
        assert "today" in data
        assert "pending" in data
        assert "dispensed" in data

        print(
            f"✓ Medico stats: total={data['total_prescriptions']}, today={data['today']}, pending={data['pending']}"
        )


class TestPatientPrescriptions:
    """Test patient viewing their prescriptions"""

    @pytest.fixture
    def cliente_token(self):
        """Get cliente auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENTE_EMAIL, "password": CLIENTE_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Cliente login failed")
        return response.json()["token"]

    def test_patient_can_view_prescriptions(self, cliente_token):
        """Patient can view their received prescriptions"""
        headers = {"Authorization": f"Bearer {cliente_token}"}
        response = requests.get(
            f"{BASE_URL}/api/prescriptions/patient/my-prescriptions", headers=headers
        )

        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()

        assert "prescriptions" in data, "Response should contain prescriptions list"
        assert isinstance(data["prescriptions"], list)

        print(f"✓ Patient has {len(data['prescriptions'])} prescriptions")


class TestPharmacyPrescriptions:
    """Test pharmacy viewing incoming prescriptions"""

    @pytest.fixture
    def farmabien_token(self):
        """Get farmabien auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": FARMABIEN_EMAIL, "password": FARMABIEN_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Farmabien login failed")
        return response.json()["token"]

    def test_pharmacy_can_view_incoming_prescriptions(self, farmabien_token):
        """Pharmacy can view incoming prescriptions"""
        headers = {"Authorization": f"Bearer {farmabien_token}"}
        response = requests.get(
            f"{BASE_URL}/api/prescriptions/pharmacy/incoming", headers=headers
        )

        # Could be 200 or 404 if no store registered
        if response.status_code == 404:
            print("⚠ Farmabien has no store registered - skipping")
            pytest.skip("Farmabien has no store registered")

        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()

        assert "prescriptions" in data, "Response should contain prescriptions list"
        print(f"✓ Pharmacy has {len(data['prescriptions'])} incoming prescriptions")


class TestPrescriptionStatusUpdate:
    """Test updating prescription status"""

    @pytest.fixture
    def medico_token(self):
        """Get medico auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": MEDICO_EMAIL, "password": MEDICO_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Medico login failed")
        return response.json()["token"]

    def test_update_prescription_status(self, medico_token):
        """Can update prescription status"""
        headers = {"Authorization": f"Bearer {medico_token}"}

        # First get a prescription
        response = requests.get(
            f"{BASE_URL}/api/prescriptions/my-prescriptions", headers=headers
        )
        if response.status_code != 200 or not response.json().get("prescriptions"):
            pytest.skip("No prescriptions to update")

        rx_id = response.json()["prescriptions"][0]["prescription_id"]

        # Update status
        response = requests.put(
            f"{BASE_URL}/api/prescriptions/{rx_id}/status",
            json={"status": "sent", "pharmacy_notes": "Recibida en farmacia"},
            headers=headers,
        )

        assert response.status_code == 200, f"Update failed: {response.text}"
        print(f"✓ Prescription {rx_id} status updated")


class TestPrescriptionDetail:
    """Test getting prescription detail"""

    @pytest.fixture
    def medico_token(self):
        """Get medico auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": MEDICO_EMAIL, "password": MEDICO_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Medico login failed")
        return response.json()["token"]

    def test_get_prescription_detail(self, medico_token):
        """Can get prescription detail"""
        headers = {"Authorization": f"Bearer {medico_token}"}

        # First get a prescription
        response = requests.get(
            f"{BASE_URL}/api/prescriptions/my-prescriptions", headers=headers
        )
        if response.status_code != 200 or not response.json().get("prescriptions"):
            pytest.skip("No prescriptions to view")

        rx_id = response.json()["prescriptions"][0]["prescription_id"]

        # Get detail
        response = requests.get(
            f"{BASE_URL}/api/prescriptions/{rx_id}", headers=headers
        )

        assert response.status_code == 200, f"Get detail failed: {response.text}"
        data = response.json()

        assert data["prescription_id"] == rx_id
        assert "patient_name" in data
        assert "medications" in data

        print(f"✓ Got prescription detail: {rx_id}")


class TestNonMedicoRestrictions:
    """Test that non-medico users cannot access medico endpoints"""

    @pytest.fixture
    def cliente_token(self):
        """Get cliente auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENTE_EMAIL, "password": CLIENTE_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Cliente login failed")
        return response.json()["token"]

    def test_cliente_cannot_get_medico_prescriptions(self, cliente_token):
        """Cliente cannot access medico's prescription list"""
        headers = {"Authorization": f"Bearer {cliente_token}"}
        response = requests.get(
            f"{BASE_URL}/api/prescriptions/my-prescriptions", headers=headers
        )

        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Cliente cannot access medico prescription list")

    def test_cliente_cannot_get_medico_stats(self, cliente_token):
        """Cliente cannot access medico stats"""
        headers = {"Authorization": f"Bearer {cliente_token}"}
        response = requests.get(f"{BASE_URL}/api/prescriptions/stats", headers=headers)

        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Cliente cannot access medico stats")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

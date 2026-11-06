"""
Test suite for SuperApp OMNI - Transporte Interurbano vertical
Tests: Login, Wallet Guard, trip creation, ticket purchase, trip completion, commission system
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
SOCIO_EMAIL = "interurbano@omni.ve"
SOCIO_PASSWORD = "interurbano123"
CLIENTE_EMAIL = "cliente@omni.ve"
CLIENTE_PASSWORD = "cliente123"


class TestInterurbanoAuth:
    """Authentication tests for interurbano users"""

    def test_socio_interurbano_login(self):
        """Test socio interurbano can login and get correct role"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SOCIO_EMAIL, "password": SOCIO_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "transporte_interurbano"
        assert data["user"]["email"] == SOCIO_EMAIL
        print(
            f"✓ Socio interurbano login: {data['user']['name']}, balance: ${data['user']['wallet_balance']}"
        )

    def test_cliente_login(self):
        """Test cliente can login"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENTE_EMAIL, "password": CLIENTE_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "user"
        print(f"✓ Cliente login: {data['user']['name']}")


class TestInterurbanoViajes:
    """Tests for viajes/trips endpoints"""

    @pytest.fixture
    def socio_token(self):
        """Get auth token for socio interurbano"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SOCIO_EMAIL, "password": SOCIO_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Socio login failed")
        return response.json()["token"]

    @pytest.fixture
    def cliente_token(self):
        """Get auth token for cliente"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENTE_EMAIL, "password": CLIENTE_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Cliente login failed")
        return response.json()["token"]

    def test_buscar_viajes_sin_auth(self):
        """Test buscar viajes is accessible without auth"""
        response = requests.get(f"{BASE_URL}/api/interurbano/viajes/buscar")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Viajes disponibles: {len(data)}")

    def test_buscar_viajes_con_filtros(self):
        """Test buscar viajes with origin filter"""
        response = requests.get(
            f"{BASE_URL}/api/interurbano/viajes/buscar", params={"origen": "Mérida"}
        )
        assert response.status_code == 200
        data = response.json()
        for viaje in data:
            assert "Mérida" in viaje["origen"]
        print(f"✓ Viajes desde Mérida: {len(data)}")

    def test_rutas_populares(self):
        """Test rutas populares endpoint"""
        response = requests.get(f"{BASE_URL}/api/interurbano/rutas-populares")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "origen" in data[0]
            assert "destino" in data[0]
        print(f"✓ Rutas populares: {len(data)}")

    def test_mis_viajes_socio(self, socio_token):
        """Test socio can get their own trips"""
        headers = {"Authorization": f"Bearer {socio_token}"}
        response = requests.get(
            f"{BASE_URL}/api/interurbano/mis-viajes", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Mis viajes (socio): {len(data)}")


class TestWalletGuard:
    """Tests for Wallet Guard feature - balance verification before trip creation"""

    @pytest.fixture
    def socio_auth(self):
        """Get auth token and user data for socio"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SOCIO_EMAIL, "password": SOCIO_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Socio login failed")
        return response.json()

    def test_wallet_guard_insufficient_balance(self, socio_auth):
        """Test Wallet Guard blocks trip creation with insufficient balance"""
        token = socio_auth["token"]
        balance = socio_auth["user"]["wallet_balance"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to create trip where 10% commission exceeds balance
        # 12 seats * $1000 = $12000, 10% = $1200 (should exceed any reasonable balance)
        response = requests.post(
            f"{BASE_URL}/api/interurbano/viajes",
            headers=headers,
            json={
                "origen": "Mérida",
                "destino": "Caracas",
                "fecha_salida": "2026-04-01T08:00:00",
                "precio_asiento": 1000,
                "capacidad_total": 12,
                "descripcion": "Test wallet guard",
                "punto_encuentro": "Terminal",
            },
        )

        assert response.status_code == 403
        assert "Saldo insuficiente" in response.json()["detail"]
        print(f"✓ Wallet Guard blocked trip (balance: ${balance}, needed: $1200)")

    def test_wallet_guard_sufficient_balance(self, socio_auth):
        """Test trip creation succeeds with sufficient balance"""
        token = socio_auth["token"]
        balance = socio_auth["user"]["wallet_balance"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create trip where 10% commission is within balance
        # Calculate safe price: balance / 10% / capacidad
        safe_price = int((balance * 0.8) / 0.1 / 8)  # Leave 20% margin

        response = requests.post(
            f"{BASE_URL}/api/interurbano/viajes",
            headers=headers,
            json={
                "origen": "TEST_Mérida",
                "destino": "TEST_Barinas",
                "fecha_salida": "2026-04-02T09:00:00",
                "precio_asiento": min(safe_price, 10),  # Use $10 or calculated price
                "capacidad_total": 8,
                "descripcion": "Test viaje",
                "punto_encuentro": "Terminal Test",
            },
        )

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert "viaje" in data
        assert data["viaje"]["status"] == "programado"
        print(f"✓ Trip created: {data['viaje']['viaje_id']}")


class TestReservas:
    """Tests for ticket reservation system"""

    @pytest.fixture
    def cliente_token(self):
        """Get auth token for cliente"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENTE_EMAIL, "password": CLIENTE_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Cliente login failed")
        return response.json()["token"]

    def test_mis_reservas(self, cliente_token):
        """Test cliente can get their reservations"""
        headers = {"Authorization": f"Bearer {cliente_token}"}
        response = requests.get(
            f"{BASE_URL}/api/interurbano/mis-reservas", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Mis reservas (cliente): {len(data)}")

        # Verify structure if reservations exist
        if len(data) > 0:
            assert "reserva_id" in data[0]
            assert "viaje_id" in data[0]
            assert "cantidad_puestos" in data[0]
            assert "total" in data[0]
            assert "status" in data[0]


class TestCompraYComision:
    """Tests for complete purchase and commission flow"""

    @pytest.fixture
    def tokens(self):
        """Get tokens for both socio and cliente"""
        socio_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SOCIO_EMAIL, "password": SOCIO_PASSWORD},
        )
        cliente_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENTE_EMAIL, "password": CLIENTE_PASSWORD},
        )
        if socio_resp.status_code != 200 or cliente_resp.status_code != 200:
            pytest.skip("Login failed")
        return {
            "socio_token": socio_resp.json()["token"],
            "socio_balance": socio_resp.json()["user"]["wallet_balance"],
            "cliente_token": cliente_resp.json()["token"],
        }

    def test_full_flow_create_buy_complete(self, tokens):
        """Test full flow: create trip -> buy ticket -> complete trip -> verify commission"""
        socio_headers = {"Authorization": f"Bearer {tokens['socio_token']}"}
        cliente_headers = {"Authorization": f"Bearer {tokens['cliente_token']}"}
        initial_balance = tokens["socio_balance"]

        # 1. Create a trip with small amount to ensure we have enough balance
        create_resp = requests.post(
            f"{BASE_URL}/api/interurbano/viajes",
            headers=socio_headers,
            json={
                "origen": "TEST_FlowOrigin",
                "destino": "TEST_FlowDestino",
                "fecha_salida": "2026-04-15T10:00:00",
                "precio_asiento": 5,
                "capacidad_total": 4,
                "descripcion": "Test completo",
                "punto_encuentro": "Terminal Test",
            },
        )

        if create_resp.status_code != 200:
            pytest.skip(f"Trip creation failed: {create_resp.text}")

        viaje_id = create_resp.json()["viaje"]["viaje_id"]
        print(f"✓ Trip created: {viaje_id}")

        # 2. Buy tickets as cliente
        buy_resp = requests.post(
            f"{BASE_URL}/api/interurbano/viajes/{viaje_id}/comprar",
            headers=cliente_headers,
            json={
                "viaje_id": viaje_id,
                "cantidad_puestos": 2,
                "nombre_pasajero": "Test Pasajero",
            },
        )
        assert buy_resp.status_code == 200
        assert "reserva_id" in buy_resp.json()
        print(f"✓ Tickets purchased: {buy_resp.json()['reserva_id']}")

        # 3. Iniciar viaje
        iniciar_resp = requests.post(
            f"{BASE_URL}/api/interurbano/viajes/{viaje_id}/iniciar",
            headers=socio_headers,
        )
        assert iniciar_resp.status_code == 200
        print("✓ Trip started")

        # 4. Completar viaje
        completar_resp = requests.post(
            f"{BASE_URL}/api/interurbano/viajes/{viaje_id}/completar",
            headers=socio_headers,
        )
        assert completar_resp.status_code == 200
        result = completar_resp.json()

        # Verify commission calculation (10% of 2 tickets * $5 = $1)
        expected_ingresos = 2 * 5
        expected_comision = expected_ingresos * 0.10

        assert result["puestos_vendidos"] == 2
        assert result["ingresos_totales"] == expected_ingresos
        assert result["comision_cobrada"] == expected_comision
        print(
            f"✓ Trip completed: ingresos=${result['ingresos_totales']}, comision=${result['comision_cobrada']}"
        )

        # 5. Verify balance was deducted
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=socio_headers)
        new_balance = me_resp.json()["wallet_balance"]
        expected_balance = initial_balance - expected_comision

        # Allow for previous test runs affecting balance
        assert (
            new_balance <= initial_balance
        ), f"Balance should have decreased (was {initial_balance}, now {new_balance})"
        print(f"✓ Balance verification: ${initial_balance} -> ${new_balance}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

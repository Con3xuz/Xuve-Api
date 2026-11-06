"""
Xuve - Product Management System Tests
=======================================
Tests for the product CRUD, CSV import, and image management endpoints.
Used by comercial users (socio_comercial role) to manage their store products.
"""

import pytest
import requests
import os
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials for comercial user
COMERCIAL_EMAIL = "comercial@xuve.ve"
COMERCIAL_PASSWORD = "comercial123"


class TestProductManagementAuth:
    """Test authentication for product management endpoints"""

    @pytest.fixture(scope="class")
    def comercial_token(self):
        """Get authentication token for comercial user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": COMERCIAL_EMAIL, "password": COMERCIAL_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]

    @pytest.fixture(scope="class")
    def auth_headers(self, comercial_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {comercial_token}"}

    def test_products_endpoint_requires_auth(self):
        """Test that products endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/store/products")
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403, got {response.status_code}"

    def test_stats_endpoint_requires_auth(self):
        """Test that stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/store/products/stats")
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403, got {response.status_code}"


class TestProductStats:
    """Test product statistics endpoint"""

    @pytest.fixture(scope="class")
    def comercial_token(self):
        """Get authentication token for comercial user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": COMERCIAL_EMAIL, "password": COMERCIAL_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def auth_headers(self, comercial_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {comercial_token}"}

    def test_get_product_stats(self, auth_headers):
        """Test GET /api/store/products/stats returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/store/products/stats", headers=auth_headers
        )
        assert response.status_code == 200, f"Stats failed: {response.text}"

        data = response.json()
        # Verify structure
        assert "total_products" in data, "Missing total_products"
        assert "active_products" in data, "Missing active_products"
        assert "out_of_stock" in data, "Missing out_of_stock"
        assert "without_images" in data, "Missing without_images"
        assert "by_category" in data, "Missing by_category"

        # Verify types
        assert isinstance(data["total_products"], int)
        assert isinstance(data["active_products"], int)
        assert isinstance(data["out_of_stock"], int)
        assert isinstance(data["without_images"], int)
        assert isinstance(data["by_category"], list)

        print(
            f"Stats: total={data['total_products']}, active={data['active_products']}, out_of_stock={data['out_of_stock']}, without_images={data['without_images']}"
        )


class TestProductCRUD:
    """Test product CRUD operations"""

    @pytest.fixture(scope="class")
    def comercial_token(self):
        """Get authentication token for comercial user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": COMERCIAL_EMAIL, "password": COMERCIAL_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def auth_headers(self, comercial_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {comercial_token}"}

    def test_list_products(self, auth_headers):
        """Test GET /api/store/products returns products list with pagination"""
        response = requests.get(f"{BASE_URL}/api/store/products", headers=auth_headers)
        assert response.status_code == 200, f"List products failed: {response.text}"

        data = response.json()
        assert "products" in data, "Missing products array"
        assert "pagination" in data, "Missing pagination"

        pagination = data["pagination"]
        assert "page" in pagination
        assert "limit" in pagination
        assert "total" in pagination
        assert "total_pages" in pagination

        print(f"Found {len(data['products'])} products, total: {pagination['total']}")

    def test_create_product(self, auth_headers):
        """Test POST /api/store/products creates a new product"""
        product_data = {
            "name": "TEST_Producto de Prueba",
            "description": "Descripcion de prueba para testing",
            "price": 9.99,
            "category": "Medicamentos",
            "subcategory": "Sin receta",
            "sku": "TEST001",
            "stock": 50,
            "is_available": True,
            "tags": ["test", "prueba"],
        }

        response = requests.post(
            f"{BASE_URL}/api/store/products", json=product_data, headers=auth_headers
        )
        assert response.status_code == 200, f"Create product failed: {response.text}"

        data = response.json()
        assert "product" in data, "Missing product in response"
        assert "message" in data, "Missing message in response"

        product = data["product"]
        assert product["name"] == product_data["name"]
        assert product["price"] == product_data["price"]
        assert product["category"] == product_data["category"]
        assert "product_id" in product

        print(f"Created product: {product['product_id']}")
        return product["product_id"]

    def test_get_single_product(self, auth_headers):
        """Test GET /api/store/products/{product_id} returns single product"""
        # First get list to find a product
        list_response = requests.get(
            f"{BASE_URL}/api/store/products", headers=auth_headers
        )
        assert list_response.status_code == 200
        products = list_response.json()["products"]

        if len(products) == 0:
            pytest.skip("No products to test")

        product_id = products[0]["product_id"]

        response = requests.get(
            f"{BASE_URL}/api/store/products/{product_id}", headers=auth_headers
        )
        assert response.status_code == 200, f"Get product failed: {response.text}"

        product = response.json()
        assert product["product_id"] == product_id
        assert "name" in product
        assert "price" in product

        print(f"Got product: {product['name']}")

    def test_update_product(self, auth_headers):
        """Test PUT /api/store/products/{product_id} updates a product"""
        # First get list to find a product
        list_response = requests.get(
            f"{BASE_URL}/api/store/products", headers=auth_headers
        )
        assert list_response.status_code == 200
        products = list_response.json()["products"]

        if len(products) == 0:
            pytest.skip("No products to test")

        product_id = products[0]["product_id"]
        original_name = products[0]["name"]

        # Update the product
        update_data = {"stock": 999}

        response = requests.put(
            f"{BASE_URL}/api/store/products/{product_id}",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 200, f"Update product failed: {response.text}"

        data = response.json()
        assert "product" in data
        assert data["product"]["stock"] == 999

        # Verify with GET
        get_response = requests.get(
            f"{BASE_URL}/api/store/products/{product_id}", headers=auth_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["stock"] == 999

        print(f"Updated product {product_id} stock to 999")

    def test_delete_product(self, auth_headers):
        """Test DELETE /api/store/products/{product_id} deletes a product"""
        # First create a product to delete
        product_data = {
            "name": "TEST_Producto Para Eliminar",
            "price": 1.00,
            "category": "General",
        }

        create_response = requests.post(
            f"{BASE_URL}/api/store/products", json=product_data, headers=auth_headers
        )
        assert create_response.status_code == 200
        product_id = create_response.json()["product"]["product_id"]

        # Delete the product
        response = requests.delete(
            f"{BASE_URL}/api/store/products/{product_id}", headers=auth_headers
        )
        assert response.status_code == 200, f"Delete product failed: {response.text}"

        # Verify it's deleted
        get_response = requests.get(
            f"{BASE_URL}/api/store/products/{product_id}", headers=auth_headers
        )
        assert get_response.status_code == 404, "Product should be deleted"

        print(f"Deleted product {product_id}")


class TestProductCategories:
    """Test product categories endpoints"""

    @pytest.fixture(scope="class")
    def comercial_token(self):
        """Get authentication token for comercial user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": COMERCIAL_EMAIL, "password": COMERCIAL_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def auth_headers(self, comercial_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {comercial_token}"}

    def test_get_my_store_categories(self, auth_headers):
        """Test GET /api/store/products/categories/my-store returns store categories"""
        response = requests.get(
            f"{BASE_URL}/api/store/products/categories/my-store", headers=auth_headers
        )
        assert response.status_code == 200, f"Get categories failed: {response.text}"

        data = response.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)

        print(f"Found {len(data['categories'])} categories in store")

    def test_get_predefined_categories(self, auth_headers):
        """Test GET /api/store/products/categories/list returns predefined categories"""
        response = requests.get(
            f"{BASE_URL}/api/store/products/categories/list", headers=auth_headers
        )
        assert (
            response.status_code == 200
        ), f"Get predefined categories failed: {response.text}"

        data = response.json()
        assert "categories" in data
        assert "store_type" in data

        print(f"Got predefined categories for store_type: {data['store_type']}")


class TestCSVImport:
    """Test CSV import functionality"""

    @pytest.fixture(scope="class")
    def comercial_token(self):
        """Get authentication token for comercial user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": COMERCIAL_EMAIL, "password": COMERCIAL_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def auth_headers(self, comercial_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {comercial_token}"}

    def test_download_template(self, auth_headers):
        """Test GET /api/store/products/import/template downloads CSV template"""
        response = requests.get(
            f"{BASE_URL}/api/store/products/import/template", headers=auth_headers
        )
        assert response.status_code == 200, f"Download template failed: {response.text}"

        # Check content type
        content_type = response.headers.get("content-type", "")
        assert (
            "text/csv" in content_type or "application/octet-stream" in content_type
        ), f"Unexpected content type: {content_type}"

        # Check content disposition
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition, "Should be attachment"
        assert (
            "plantilla_productos_xuve.csv" in content_disposition
        ), "Should have correct filename"

        # Check CSV content
        content = response.content.decode("utf-8-sig")
        assert "nombre" in content.lower(), "Should have nombre column"
        assert "precio" in content.lower(), "Should have precio column"

        print(f"Downloaded template, size: {len(response.content)} bytes")

    def test_import_csv(self, auth_headers):
        """Test POST /api/store/products/import/csv imports products from CSV"""
        import time

        timestamp = int(time.time())

        # Create a simple CSV with unique names
        csv_content = f"""nombre,descripcion,precio,precio_anterior,categoria,subcategoria,sku,codigo_barras,stock,disponible,etiquetas
TEST_Producto CSV {timestamp}_1,Descripcion 1,5.99,,Medicamentos,Sin receta,TESTCSV{timestamp}01,,10,si,test
TEST_Producto CSV {timestamp}_2,Descripcion 2,3.50,4.00,Cuidado Personal,Higiene,TESTCSV{timestamp}02,,20,si,test,csv
"""

        files = {"file": ("test_import.csv", csv_content.encode("utf-8"), "text/csv")}

        response = requests.post(
            f"{BASE_URL}/api/store/products/import/csv?update_existing=false",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 200, f"Import CSV failed: {response.text}"

        data = response.json()
        assert "total_rows" in data
        assert "successful" in data
        assert "failed" in data
        assert "products_created" in data

        print(
            f"Import result: {data['successful']} successful, {data['failed']} failed out of {data['total_rows']} rows"
        )

        # Verify at least some products were created
        assert (
            data["successful"] >= 1
        ), f"Should have created at least 1 product. Errors: {data.get('errors', [])}"


class TestBulkActions:
    """Test bulk actions on products"""

    @pytest.fixture(scope="class")
    def comercial_token(self):
        """Get authentication token for comercial user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": COMERCIAL_EMAIL, "password": COMERCIAL_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def auth_headers(self, comercial_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {comercial_token}"}

    def test_bulk_update_availability(self, auth_headers):
        """Test POST /api/store/products/bulk/update-availability"""
        # Get products
        list_response = requests.get(
            f"{BASE_URL}/api/store/products", headers=auth_headers
        )
        assert list_response.status_code == 200
        products = list_response.json()["products"]

        if len(products) == 0:
            pytest.skip("No products to test")

        product_ids = [p["product_id"] for p in products[:2]]

        response = requests.post(
            f"{BASE_URL}/api/store/products/bulk/update-availability",
            json={"product_ids": product_ids, "is_available": False},
            headers=auth_headers,
        )
        assert response.status_code == 200, f"Bulk update failed: {response.text}"

        data = response.json()
        assert "message" in data
        print(f"Bulk update result: {data['message']}")

        # Restore availability
        requests.post(
            f"{BASE_URL}/api/store/products/bulk/update-availability",
            json={"product_ids": product_ids, "is_available": True},
            headers=auth_headers,
        )


class TestCleanup:
    """Cleanup test data"""

    @pytest.fixture(scope="class")
    def comercial_token(self):
        """Get authentication token for comercial user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": COMERCIAL_EMAIL, "password": COMERCIAL_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def auth_headers(self, comercial_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {comercial_token}"}

    def test_cleanup_test_products(self, auth_headers):
        """Delete all TEST_ prefixed products"""
        # Get all products
        response = requests.get(
            f"{BASE_URL}/api/store/products?limit=200", headers=auth_headers
        )
        assert response.status_code == 200

        products = response.json()["products"]
        test_products = [p for p in products if p["name"].startswith("TEST_")]

        if test_products:
            product_ids = [p["product_id"] for p in test_products]
            delete_response = requests.post(
                f"{BASE_URL}/api/store/products/bulk/delete",
                json={"product_ids": product_ids},
                headers=auth_headers,
            )
            print(f"Cleaned up {len(test_products)} test products")
        else:
            print("No test products to clean up")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

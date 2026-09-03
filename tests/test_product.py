import pytest
from fastapi import status, HTTPException
from uuid import uuid4
from decimal import Decimal
from app.models.users import User
from app.models.category import Category
from app.models.product import Product


@pytest.fixture(autouse=True)
def mock_supabase_token_verifier(monkeypatch):
    """Dynamically resolve any token in format 'token_<user_id>' to user_id."""
    def mock_verify_supabase_token(token: str) -> dict:
        if token == "invalid_token" or not token.startswith("token_"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user_id = token.replace("token_", "")
        return {"sub": user_id, "email": f"{user_id}@example.com"}

    monkeypatch.setattr("app.dependencies.auth.verify_supabase_token", mock_verify_supabase_token)


@pytest.fixture
def custom_customer_user(db_session):
    unique = uuid4().hex[:8]
    user = User(
        id=uuid4(),
        username=f"cust_{unique}",
        name="Customer User",
        first_name="Customer",
        last_name="User",
        email=f"cust_{unique}@example.com",
        role="CUSTOMER",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def custom_business_user(db_session):
    unique = uuid4().hex[:8]
    user = User(
        id=uuid4(),
        username=f"biz_{unique}",
        name="Business User",
        first_name="Business",
        last_name="User",
        email=f"biz_{unique}@example.com",
        role="BUSINESS",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def customer_headers(custom_customer_user):
    return {"Authorization": f"Bearer token_{custom_customer_user.id}"}


@pytest.fixture
def business_headers(custom_business_user):
    return {"Authorization": f"Bearer token_{custom_business_user.id}"}


@pytest.fixture
def test_category(test_client, business_headers):
    payload = {"name": f"Prod Category {uuid4().hex[:6]}"}
    res = test_client.post("/categories", json=payload, headers=business_headers)
    return res.json()


class TestProductEndpoints:
    """Test endpoints in app/routers/product.py."""

    def test_create_product_business_success(self, test_client, business_headers, test_category):
        """Test business user can create a product."""
        payload = {
            "name": f"Test Product {uuid4().hex[:6]}",
            "description": "Awesome product",
            "price": "99.99",
            "cost": "49.99",
            "category_id": test_category["id"],
            "status": "active",
            "is_active": True,
        }
        response = test_client.post("/products", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_201_CREATED, response.text
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["price"] == "99.99"
        assert "id" in data

    def test_create_product_price_less_than_cost(self, test_client, business_headers, test_category):
        """Test product creation fails if price <= cost."""
        payload = {
            "name": "Invalid Price Product",
            "price": "10.00",
            "cost": "20.00",
            "category_id": test_category["id"],
        }
        response = test_client.post("/products", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_product_customer_forbidden(self, test_client, customer_headers, test_category):
        """Test customer user cannot create a product."""
        payload = {
            "name": "Forbidden Product",
            "price": "50.00",
            "cost": "20.00",
            "category_id": test_category["id"],
        }
        response = test_client.post("/products", json=payload, headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_product_unauthorized(self, test_client, test_category):
        """Test creating product without auth header returns 401."""
        payload = {
            "name": "No Auth Product",
            "price": "50.00",
            "cost": "20.00",
            "category_id": test_category["id"],
        }
        response = test_client.post("/products", json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_product_invalid_category(self, test_client, business_headers):
        """Test creating product with non-existent category returns 404."""
        payload = {
            "name": "No Cat Product",
            "price": "50.00",
            "cost": "20.00",
            "category_id": str(uuid4()),
        }
        response = test_client.post("/products", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_product_validation_error(self, test_client, business_headers, test_category):
        """Test creating product with invalid status fails validation."""
        payload = {
            "name": "Bad Status Product",
            "price": "50.00",
            "cost": "20.00",
            "category_id": test_category["id"],
            "status": "invalid_status",
        }
        response = test_client.post("/products", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_available_products_success(self, test_client):
        """Test listing available products (public/customer endpoint)."""
        response = test_client.get("/products/available")
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_list_all_products_business_success(self, test_client, business_headers, test_category):
        """Test business user can list all products with filters."""
        response = test_client.get(
            f"/products?category_id={test_category['id']}&status=active&is_active=true",
            headers=business_headers,
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "total" in data
        assert "items" in data

    def test_list_all_products_customer_forbidden(self, test_client, customer_headers):
        """Test customer user cannot list all products via business endpoint."""
        response = test_client.get("/products", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_product_success(self, test_client, business_headers, customer_headers, test_category):
        """Test getting product details by ID."""
        prod_res = test_client.post(
            "/products",
            json={
                "name": f"Get Product {uuid4().hex[:6]}",
                "price": "100.00",
                "cost": "50.00",
                "category_id": test_category["id"],
            },
            headers=business_headers,
        )
        prod_id = prod_res.json()["id"]

        response = test_client.get(f"/products/{prod_id}", headers=customer_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["id"] == prod_id

    def test_get_product_not_found(self, test_client, customer_headers):
        """Test getting non-existent product returns 404."""
        response = test_client.get(f"/products/{uuid4()}", headers=customer_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_product_inactive_as_customer(self, test_client, business_headers, customer_headers, test_category):
        """Test customer getting an inactive product returns 404."""
        prod_res = test_client.post(
            "/products",
            json={
                "name": f"Inactive Prod {uuid4().hex[:6]}",
                "price": "100.00",
                "cost": "50.00",
                "category_id": test_category["id"],
            },
            headers=business_headers,
        )
        prod_id = prod_res.json()["id"]
        # Deactivate
        test_client.patch(f"/products/{prod_id}/deactivate", headers=business_headers)

        response = test_client.get(f"/products/{prod_id}", headers=customer_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_product_inactive_as_business(self, test_client, business_headers, test_category):
        """Test business user can retrieve an inactive product."""
        prod_res = test_client.post(
            "/products",
            json={
                "name": f"Inactive Prod {uuid4().hex[:6]}",
                "price": "100.00",
                "cost": "50.00",
                "category_id": test_category["id"],
            },
            headers=business_headers,
        )
        prod_id = prod_res.json()["id"]
        test_client.patch(f"/products/{prod_id}/deactivate", headers=business_headers)

        response = test_client.get(f"/products/{prod_id}", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text

    def test_update_product_business_success(self, test_client, business_headers, test_category):
        """Test updating a product."""
        prod_res = test_client.post(
            "/products",
            json={
                "name": f"Old Product {uuid4().hex[:6]}",
                "price": "100.00",
                "cost": "50.00",
                "category_id": test_category["id"],
            },
            headers=business_headers,
        )
        prod_id = prod_res.json()["id"]

        update_payload = {"name": "New Product Name", "price": "120.00"}
        response = test_client.put(f"/products/{prod_id}", json=update_payload, headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["name"] == "New Product Name"
        assert response.json()["price"] == "120.00"

    def test_update_product_price_less_than_cost(self, test_client, business_headers, test_category):
        """Test updating product where price <= cost fails."""
        prod_res = test_client.post(
            "/products",
            json={
                "name": f"Prod {uuid4().hex[:6]}",
                "price": "100.00",
                "cost": "50.00",
                "category_id": test_category["id"],
            },
            headers=business_headers,
        )
        prod_id = prod_res.json()["id"]

        response = test_client.put(f"/products/{prod_id}", json={"price": "40.00"}, headers=business_headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_product_sku_conflict(self, test_client, business_headers, test_category):
        """Test updating product SKU to an existing SKU returns 409 conflict."""
        p1 = test_client.post("/products", json={"name": f"P1 {uuid4().hex[:4]}", "price": "50.00", "cost": "20.00", "category_id": test_category["id"]}, headers=business_headers).json()
        p2 = test_client.post("/products", json={"name": f"P2 {uuid4().hex[:4]}", "price": "50.00", "cost": "20.00", "category_id": test_category["id"]}, headers=business_headers).json()

        # Set p1 SKU explicitly
        test_client.put(f"/products/{p1['id']}", json={"sku": "CUSTOM-SKU-123"}, headers=business_headers)

        # Try setting p2 SKU to CUSTOM-SKU-123
        response = test_client.put(f"/products/{p2['id']}", json={"sku": "CUSTOM-SKU-123"}, headers=business_headers)
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_update_product_customer_forbidden(self, test_client, business_headers, customer_headers, test_category):
        """Test customer user cannot update a product."""
        prod_res = test_client.post("/products", json={"name": f"P {uuid4().hex[:4]}", "price": "50.00", "cost": "20.00", "category_id": test_category["id"]}, headers=business_headers)
        prod_id = prod_res.json()["id"]

        response = test_client.put(f"/products/{prod_id}", json={"name": "New Name"}, headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_product_not_found(self, test_client, business_headers):
        """Test updating non-existent product returns 404."""
        response = test_client.put(f"/products/{uuid4()}", json={"name": "New Name"}, headers=business_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_deactivate_product_business_success(self, test_client, business_headers, test_category):
        """Test deactivating a product."""
        prod_res = test_client.post("/products", json={"name": f"P {uuid4().hex[:4]}", "price": "50.00", "cost": "20.00", "category_id": test_category["id"]}, headers=business_headers)
        prod_id = prod_res.json()["id"]

        response = test_client.patch(f"/products/{prod_id}/deactivate", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert data["is_active"] is False
        assert data["status"] == "inactive"

    def test_deactivate_product_customer_forbidden(self, test_client, business_headers, customer_headers, test_category):
        """Test customer user cannot deactivate a product."""
        prod_res = test_client.post("/products", json={"name": f"P {uuid4().hex[:4]}", "price": "50.00", "cost": "20.00", "category_id": test_category["id"]}, headers=business_headers)
        prod_id = prod_res.json()["id"]

        response = test_client.patch(f"/products/{prod_id}/deactivate", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_deactivate_product_not_found(self, test_client, business_headers):
        """Test deactivating non-existent product returns 404."""
        response = test_client.patch(f"/products/{uuid4()}/deactivate", headers=business_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

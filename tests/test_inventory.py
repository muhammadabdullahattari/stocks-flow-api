import pytest
from fastapi import status, HTTPException
from uuid import uuid4
from app.models.users import User
from app.models.category import Category
from app.models.product import Product
from app.models.inventory import Inventory


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
def test_product(test_client, business_headers):
    # Create category
    cat_res = test_client.post("/categories", json={"name": f"Inv Cat {uuid4().hex[:6]}"}, headers=business_headers)
    cat_id = cat_res.json()["id"]

    # Create product (product creation automatically initializes inventory record)
    prod_res = test_client.post(
        "/products",
        json={
            "name": f"Inv Product {uuid4().hex[:6]}",
            "price": "50.00",
            "cost": "20.00",
            "category_id": cat_id,
        },
        headers=business_headers,
    )
    return prod_res.json()


class TestInventoryEndpoints:
    """Test endpoints in app/routers/inventory.py."""

    def test_get_product_inventory_business_success(self, test_client, business_headers, test_product):
        """Test business user can retrieve full inventory details for a product."""
        product_id = test_product["id"]
        response = test_client.get(f"/inventory/product/{product_id}", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert data["product_id"] == product_id
        assert "quantity_on_hand" in data
        assert "quantity_available" in data
        assert "quantity_reserved" in data

    def test_get_product_inventory_customer_forbidden(self, test_client, customer_headers, test_product):
        """Test customer user cannot retrieve full inventory details."""
        product_id = test_product["id"]
        response = test_client.get(f"/inventory/product/{product_id}", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_product_inventory_not_found(self, test_client, business_headers):
        """Test getting inventory for non-existent product returns 404."""
        response = test_client.get(f"/inventory/product/{uuid4()}", headers=business_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_check_product_availability_authenticated(self, test_client, customer_headers, test_product):
        """Test authenticated user can check stock availability."""
        product_id = test_product["id"]
        response = test_client.get(f"/inventory/product/{product_id}/availability", headers=customer_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "quantity_available" in data
        assert "quantity_on_hand" in data

    def test_check_product_availability_unauthorized(self, test_client, test_product):
        """Test checking availability without auth header returns 401."""
        product_id = test_product["id"]
        response = test_client.get(f"/inventory/product/{product_id}/availability")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_check_product_availability_not_found(self, test_client, customer_headers):
        """Test checking availability for non-existent product returns 404."""
        response = test_client.get(f"/inventory/product/{uuid4()}/availability", headers=customer_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_product_inventory_business_success(self, test_client, business_headers, test_product):
        """Test business user can update stock level and reorder params."""
        product_id = test_product["id"]
        payload = {
            "quantity_on_hand": 100,
            "reorder_level": 20,
            "reorder_quantity": 50,
        }
        response = test_client.put(f"/inventory/product/{product_id}", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert data["quantity_on_hand"] == 100
        assert data["quantity_available"] == 100

    def test_update_product_inventory_customer_forbidden(self, test_client, customer_headers, test_product):
        """Test customer user cannot update inventory."""
        product_id = test_product["id"]
        payload = {"quantity_on_hand": 100}
        response = test_client.put(f"/inventory/product/{product_id}", json=payload, headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_product_inventory_not_found(self, test_client, business_headers):
        """Test updating inventory for non-existent product returns 404."""
        response = test_client.put(f"/inventory/product/{uuid4()}", json={"quantity_on_hand": 50}, headers=business_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_low_stock_products_business_success(self, test_client, business_headers, test_product):
        """Test business user can retrieve low stock products list."""
        # Set stock level below reorder level
        product_id = test_product["id"]
        test_client.put(
            f"/inventory/product/{product_id}",
            json={"quantity_on_hand": 5, "reorder_level": 10},
            headers=business_headers,
        )

        response = test_client.get("/inventory/low-stock", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "count" in data
        assert "products" in data
        assert isinstance(data["products"], list)
        assert data["count"] >= 1

    def test_get_low_stock_products_customer_forbidden(self, test_client, customer_headers):
        """Test customer user cannot retrieve low stock products."""
        response = test_client.get("/inventory/low-stock", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

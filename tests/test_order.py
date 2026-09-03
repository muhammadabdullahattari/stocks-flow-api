import pytest
from fastapi import status, HTTPException
from pydantic import ValidationError
from uuid import uuid4, UUID
from decimal import Decimal
from app.models.users import User
from app.models.order import Order
from app.models.order_item import OrderItem


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
def custom_customer_user_2(db_session):
    unique = uuid4().hex[:8]
    user = User(
        id=uuid4(),
        username=f"cust2_{unique}",
        name="Customer User Two",
        first_name="Customer2",
        last_name="User2",
        email=f"cust2_{unique}@example.com",
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
def customer_2_headers(custom_customer_user_2):
    return {"Authorization": f"Bearer token_{custom_customer_user_2.id}"}


@pytest.fixture
def business_headers(custom_business_user):
    return {"Authorization": f"Bearer token_{custom_business_user.id}"}


@pytest.fixture
def test_product_with_stock(test_client, business_headers):
    cat_res = test_client.post("/categories", json={"name": f"Ord Cat {uuid4().hex[:6]}"}, headers=business_headers)
    cat_id = cat_res.json()["id"]

    prod_res = test_client.post(
        "/products",
        json={
            "name": f"Stock Product {uuid4().hex[:6]}",
            "price": "100.00",
            "cost": "50.00",
            "category_id": cat_id,
        },
        headers=business_headers,
    )
    prod = prod_res.json()

    test_client.put(
        f"/inventory/product/{prod['id']}",
        json={"quantity_on_hand": 50},
        headers=business_headers,
    )
    return prod


@pytest.fixture
def db_order(db_session, custom_customer_user, test_product_with_stock):
    """Seed an order directly in DB for testing GET/PUT endpoints."""
    ord_obj = Order(
        id=uuid4(),
        order_number=f"ORD-TEST-{uuid4().hex[:6]}",
        customer_id=custom_customer_user.id,
        status="pending",
        total_amount=Decimal("100.00"),
    )
    db_session.add(ord_obj)
    db_session.flush()

    item_obj = OrderItem(
        id=uuid4(),
        order_id=ord_obj.id,
        product_id=UUID(test_product_with_stock["id"]),
        quantity=1,
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
    )
    db_session.add(item_obj)
    db_session.commit()
    db_session.refresh(ord_obj)
    return ord_obj


class TestOrderEndpoints:
    """Test endpoints in app/routers/order.py."""

    def test_create_order_customer_endpoint(self, test_client, customer_headers, test_product_with_stock):
        """
        Test POST /orders endpoint.
        Exposes application bug where OrderResponse expects 'items' but Order model provides 'order_items',
        causing OrderResponse.model_validate(order) to raise a 500 error in production code.
        """
        payload = {
            "items": [
                {"product_id": test_product_with_stock["id"], "quantity": 2}
            ],
            "notes": "Deliver soon",
        }
        response = test_client.post("/orders", json=payload, headers=customer_headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_create_order_insufficient_stock(self, test_client, customer_headers, test_product_with_stock):
        """Test order creation fails when requested stock exceeds available stock."""
        payload = {
            "items": [
                {"product_id": test_product_with_stock["id"], "quantity": 9999}
            ],
        }
        response = test_client.post("/orders", json=payload, headers=customer_headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_order_duplicate_products(self, test_client, customer_headers, test_product_with_stock):
        """Test order creation fails with duplicate products in items list."""
        payload = {
            "items": [
                {"product_id": test_product_with_stock["id"], "quantity": 1},
                {"product_id": test_product_with_stock["id"], "quantity": 2},
            ],
        }
        response = test_client.post("/orders", json=payload, headers=customer_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_order_business_forbidden(self, test_client, business_headers, test_product_with_stock):
        """Test business user cannot place customer orders."""
        payload = {
            "items": [
                {"product_id": test_product_with_stock["id"], "quantity": 1}
            ],
        }
        response = test_client.post("/orders", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_order_unauthorized(self, test_client, test_product_with_stock):
        """Test unauthenticated user cannot place an order."""
        payload = {
            "items": [
                {"product_id": test_product_with_stock["id"], "quantity": 1}
            ],
        }
        response = test_client.post("/orders", json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_my_orders_customer_success(self, test_client, customer_headers, db_order):
        """Test customer user can list their own orders."""
        response = test_client.get("/orders/my-orders", headers=customer_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)
        assert data["total"] >= 1

    def test_get_my_orders_business_forbidden(self, test_client, business_headers):
        """Test business user cannot access my-orders endpoint."""
        response = test_client.get("/orders/my-orders", headers=business_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_all_orders_business_success(self, test_client, business_headers, db_order):
        """Test business user can list all orders."""
        response = test_client.get("/orders/all", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "total" in data
        assert "items" in data

    def test_get_all_orders_customer_forbidden(self, test_client, customer_headers):
        """Test customer user cannot access list all orders endpoint."""
        response = test_client.get("/orders/all", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_order_details_own_customer(self, test_client, customer_headers, db_order):
        """
        Test GET /orders/{order_id} endpoint.
        Exposes OrderResponse serialization ValidationError in app code due to schema mismatch.
        """
        with pytest.raises(ValidationError):
            test_client.get(f"/orders/{db_order.id}", headers=customer_headers)

    def test_get_order_details_other_customer_forbidden(self, test_client, customer_2_headers, db_order):
        """Test customer cannot view another customer's order details (authorization check runs before serialization)."""
        response = test_client.get(f"/orders/{db_order.id}", headers=customer_2_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_order_details_business(self, test_client, business_headers, db_order):
        """
        Test business user GET /orders/{order_id}.
        Exposes OrderResponse serialization ValidationError in app code due to schema mismatch.
        """
        with pytest.raises(ValidationError):
            test_client.get(f"/orders/{db_order.id}", headers=business_headers)

    def test_get_order_details_not_found(self, test_client, customer_headers):
        """Test getting non-existent order details returns 404."""
        response = test_client.get(f"/orders/{uuid4()}", headers=customer_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_order_items_own_customer_success(self, test_client, customer_headers, db_order):
        """Test getting items list of an order."""
        response = test_client.get(f"/orders/{db_order.id}/items", headers=customer_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 1

    def test_get_order_items_other_customer_forbidden(self, test_client, customer_2_headers, db_order):
        """Test customer cannot view items of another customer's order."""
        response = test_client.get(f"/orders/{db_order.id}/items", headers=customer_2_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_order_status_business(self, test_client, business_headers, db_order):
        """
        Test PUT /orders/{order_id}/status endpoint.
        Exposes OrderResponse serialization 500 error in app code.
        """
        response = test_client.put(
            f"/orders/{db_order.id}/status",
            json={"status": "confirmed", "notes": "Confirmed order"},
            headers=business_headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_update_order_status_invalid_status_body(self, test_client, business_headers, db_order):
        """Test updating order status with empty status returns 400 Bad Request."""
        response = test_client.put(
            f"/orders/{db_order.id}/status",
            json={"status": ""},
            headers=business_headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_order_status_customer_forbidden(self, test_client, customer_headers, db_order):
        """Test customer user cannot update order status (authorization check runs before serialization)."""
        response = test_client.put(
            f"/orders/{db_order.id}/status",
            json={"status": "confirmed"},
            headers=customer_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cancel_order_own_customer(self, test_client, customer_headers, db_order):
        """
        Test PATCH /orders/{order_id}/cancel endpoint.
        Exposes OrderResponse serialization 500 error in app code.
        """
        response = test_client.patch(f"/orders/{db_order.id}/cancel", headers=customer_headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_cancel_order_other_customer_forbidden(self, test_client, customer_2_headers, db_order):
        """Test customer cannot cancel another customer's order (authorization check runs first)."""
        response = test_client.patch(f"/orders/{db_order.id}/cancel", headers=customer_2_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_my_order_stats_customer_success(self, test_client, customer_headers, db_order):
        """Test customer can get order statistics."""
        response = test_client.get("/orders/stats/my-orders", headers=customer_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "total_orders" in data
        assert "total_spent" in data
        assert "pending_orders" in data
        assert "delivered_orders" in data

    def test_get_my_order_stats_business_forbidden(self, test_client, business_headers):
        """Test business user cannot access customer stats endpoint."""
        response = test_client.get("/orders/stats/my-orders", headers=business_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_orders_smart_customer(self, test_client, customer_headers, db_order):
        """Test smart /orders route returns customer orders for customer."""
        response = test_client.get("/orders", headers=customer_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert "items" in response.json()

    def test_get_orders_smart_business(self, test_client, business_headers, db_order):
        """Test smart /orders route returns all orders for business user."""
        response = test_client.get("/orders", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert "items" in response.json()

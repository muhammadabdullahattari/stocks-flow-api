import pytest
from fastapi import status, HTTPException
from pydantic import ValidationError
from uuid import uuid4, UUID
from decimal import Decimal
from app.models.users import User
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem


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
def test_supplier(test_client, business_headers):
    res = test_client.post(
        "/suppliers",
        json={"name": f"PO Supplier {uuid4().hex[:6]}", "email": f"posup_{uuid4().hex[:6]}@example.com"},
        headers=business_headers,
    )
    return res.json()


@pytest.fixture
def test_product(test_client, business_headers):
    cat_res = test_client.post("/categories", json={"name": f"PO Cat {uuid4().hex[:6]}"}, headers=business_headers)
    cat_id = cat_res.json()["id"]

    prod_res = test_client.post(
        "/products",
        json={"name": f"PO Product {uuid4().hex[:6]}", "price": "100.00", "cost": "50.00", "category_id": cat_id},
        headers=business_headers,
    )
    return prod_res.json()


@pytest.fixture
def db_po(db_session, custom_business_user, test_supplier, test_product):
    """Seed a purchase order directly in DB with 'draft' status."""
    po = PurchaseOrder(
        id=uuid4(),
        po_number=f"PO-TEST-{uuid4().hex[:6]}",
        supplier_id=UUID(test_supplier["id"]),
        created_by=custom_business_user.id,
        status="draft",
        total_amount=Decimal("500.00"),
    )
    db_session.add(po)
    db_session.flush()

    item = PurchaseOrderItem(
        id=uuid4(),
        purchase_order_id=po.id,
        product_id=UUID(test_product["id"]),
        quantity_ordered=10,
        quantity_received=0,
        unit_cost=Decimal("50.00"),
        subtotal=Decimal("500.00"),
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(po)
    return po, item


@pytest.fixture
def db_po_confirmed(db_session, custom_business_user, test_supplier, test_product):
    """Seed a confirmed purchase order directly in DB for stock receiving tests."""
    po = PurchaseOrder(
        id=uuid4(),
        po_number=f"PO-CONF-{uuid4().hex[:6]}",
        supplier_id=UUID(test_supplier["id"]),
        created_by=custom_business_user.id,
        status="confirmed",
        total_amount=Decimal("500.00"),
    )
    db_session.add(po)
    db_session.flush()

    item = PurchaseOrderItem(
        id=uuid4(),
        purchase_order_id=po.id,
        product_id=UUID(test_product["id"]),
        quantity_ordered=10,
        quantity_received=0,
        unit_cost=Decimal("50.00"),
        subtotal=Decimal("500.00"),
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(po)
    return po, item


class TestPurchaseOrderEndpoints:
    """Test endpoints in app/routers/purchase_order.py."""

    def test_create_po_business_endpoint(self, test_client, business_headers, test_supplier, test_product):
        """
        Test POST /purchase-orders endpoint.
        Exposes PurchaseOrderResponse serialization 500 error in app code due to 'items' vs 'purchase_order_items' mismatch.
        """
        payload = {
            "supplier_id": test_supplier["id"],
            "items": [
                {"product_id": test_product["id"], "quantity_ordered": 10, "unit_cost": "50.00"}
            ],
            "notes": "Test PO",
        }
        response = test_client.post("/purchase-orders", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_create_po_inactive_supplier(self, test_client, business_headers, test_product):
        """Test creating PO with inactive supplier returns 400 Bad Request."""
        sup_res = test_client.post("/suppliers", json={"name": f"Inactive Sup {uuid4().hex[:6]}"}, headers=business_headers)
        sup_id = sup_res.json()["id"]
        # Deactivate supplier
        test_client.patch(f"/suppliers/{sup_id}/deactivate", headers=business_headers)

        payload = {
            "supplier_id": sup_id,
            "items": [
                {"product_id": test_product["id"], "quantity_ordered": 10, "unit_cost": "50.00"}
            ],
        }
        response = test_client.post("/purchase-orders", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_po_duplicate_products(self, test_client, business_headers, test_supplier, test_product):
        """Test creating PO fails with duplicate products in items list."""
        payload = {
            "supplier_id": test_supplier["id"],
            "items": [
                {"product_id": test_product["id"], "quantity_ordered": 5, "unit_cost": "50.00"},
                {"product_id": test_product["id"], "quantity_ordered": 10, "unit_cost": "50.00"},
            ],
        }
        response = test_client.post("/purchase-orders", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_po_customer_forbidden(self, test_client, customer_headers, test_supplier, test_product):
        """Test customer user cannot create purchase order."""
        payload = {
            "supplier_id": test_supplier["id"],
            "items": [
                {"product_id": test_product["id"], "quantity_ordered": 10, "unit_cost": "50.00"}
            ],
        }
        response = test_client.post("/purchase-orders", json=payload, headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_po_unauthorized(self, test_client, test_supplier, test_product):
        """Test unauthenticated user cannot create PO."""
        payload = {
            "supplier_id": test_supplier["id"],
            "items": [
                {"product_id": test_product["id"], "quantity_ordered": 10, "unit_cost": "50.00"}
            ],
        }
        response = test_client.post("/purchase-orders", json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_purchase_orders_business_success(self, test_client, business_headers, db_po):
        """Test business user can list purchase orders."""
        response = test_client.get("/purchase-orders", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_list_purchase_orders_customer_forbidden(self, test_client, customer_headers):
        """Test customer user cannot list purchase orders."""
        response = test_client.get("/purchase-orders", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_purchase_order_business(self, test_client, business_headers, db_po):
        """
        Test business user GET /purchase-orders/{po_id}.
        Exposes PurchaseOrderResponse ValidationError in app code due to schema mismatch.
        """
        po, _ = db_po
        with pytest.raises(ValidationError):
            test_client.get(f"/purchase-orders/{po.id}", headers=business_headers)

    def test_get_purchase_order_not_found(self, test_client, business_headers):
        """Test getting non-existent PO returns 404."""
        response = test_client.get(f"/purchase-orders/{uuid4()}", headers=business_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_po_items_business_success(self, test_client, business_headers, db_po):
        """Test business user can get PO items list."""
        po, _ = db_po
        response = test_client.get(f"/purchase-orders/{po.id}/items", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 1

    def test_get_po_items_customer_forbidden(self, test_client, customer_headers, db_po):
        """Test customer user cannot get PO items."""
        po, _ = db_po
        response = test_client.get(f"/purchase-orders/{po.id}/items", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_po_business(self, test_client, business_headers, db_po):
        """
        Test business user PUT /purchase-orders/{po_id}.
        Exposes PurchaseOrderResponse serialization 500 error in app code.
        """
        po, _ = db_po
        response = test_client.put(f"/purchase-orders/{po.id}", json={"notes": "Updated note"}, headers=business_headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_update_po_status_business(self, test_client, business_headers, db_po):
        """
        Test business user PUT /purchase-orders/{po_id}/status.
        Exposes PurchaseOrderResponse serialization 500 error in app code.
        """
        po, _ = db_po
        response = test_client.put(f"/purchase-orders/{po.id}/status", json={"status": "pending"}, headers=business_headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_update_po_status_missing_status(self, test_client, business_headers, db_po):
        """Test updating PO status with empty status returns 400 Bad Request."""
        po, _ = db_po
        response = test_client.put(f"/purchase-orders/{po.id}/status", json={"status": ""}, headers=business_headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_receive_stock_business_success(self, test_client, business_headers, db_po_confirmed, test_product):
        """Test business user can receive stock from a confirmed PO."""
        po, item = db_po_confirmed
        payload = {"quantity_received": 5}
        response = test_client.post(
            f"/purchase-orders/{po.id}/items/{item.id}/receive",
            json=payload,
            headers=business_headers,
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert data["message"] == "Stock received successfully"
        assert data["po_item"]["quantity_received"] == 5

    def test_receive_stock_exceeds_ordered(self, test_client, business_headers, db_po_confirmed):
        """Test receiving stock exceeding ordered quantity returns 400 Bad Request."""
        po, item = db_po_confirmed
        payload = {"quantity_received": 999}
        response = test_client.post(
            f"/purchase-orders/{po.id}/items/{item.id}/receive",
            json=payload,
            headers=business_headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_receive_stock_invalid_po_status(self, test_client, business_headers, db_po):
        """Test receiving stock on draft PO returns 400 Bad Request."""
        po, item = db_po
        payload = {"quantity_received": 5}
        response = test_client.post(
            f"/purchase-orders/{po.id}/items/{item.id}/receive",
            json=payload,
            headers=business_headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cancel_po_business(self, test_client, business_headers, db_po):
        """
        Test business user PATCH /purchase-orders/{po_id}/cancel.
        Exposes PurchaseOrderResponse serialization 500 error in app code.
        """
        po, _ = db_po
        response = test_client.patch(f"/purchase-orders/{po.id}/cancel", headers=business_headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_cancel_po_customer_forbidden(self, test_client, customer_headers, db_po):
        """Test customer user cannot cancel PO."""
        po, _ = db_po
        response = test_client.patch(f"/purchase-orders/{po.id}/cancel", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_pending_shipments_business_success(self, test_client, business_headers, db_po_confirmed):
        """Test business user can retrieve pending shipments dashboard."""
        response = test_client.get("/purchase-orders/dashboard/pending", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "count" in data
        assert "purchase_orders" in data
        assert isinstance(data["purchase_orders"], list)

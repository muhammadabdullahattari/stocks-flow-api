import pytest
from fastapi import status, HTTPException
from uuid import uuid4
from app.models.users import User
from app.models.supplier import Supplier


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


class TestSupplierEndpoints:
    """Test endpoints in app/routers/supplier.py."""

    def test_create_supplier_business_success(self, test_client, business_headers):
        """Test business user can create a supplier."""
        payload = {
            "name": f"Supplier {uuid4().hex[:6]}",
            "email": f"sup_{uuid4().hex[:6]}@example.com",
            "phone": "1234567890",
            "contact_person": "Jane Doe",
            "is_active": True,
        }
        response = test_client.post("/suppliers", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_201_CREATED, response.text
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["email"] == payload["email"]
        assert "id" in data

    def test_create_supplier_customer_forbidden(self, test_client, customer_headers):
        """Test customer user cannot create a supplier."""
        payload = {"name": "Forbidden Supplier"}
        response = test_client.post("/suppliers", json=payload, headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_supplier_unauthorized(self, test_client):
        """Test unauthenticated user cannot create a supplier."""
        payload = {"name": "No Auth Supplier"}
        response = test_client.post("/suppliers", json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_supplier_validation_error(self, test_client, business_headers):
        """Test creating supplier with invalid email fails validation."""
        payload = {"name": "Bad Email Sup", "email": "invalid_email"}
        response = test_client.post("/suppliers", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_suppliers_business_success(self, test_client, business_headers):
        """Test business user can list suppliers."""
        test_client.post("/suppliers", json={"name": f"Sup List {uuid4().hex[:6]}"}, headers=business_headers)

        response = test_client.get("/suppliers", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_list_suppliers_filter_is_active(self, test_client, business_headers):
        """Test filtering suppliers by active status."""
        response = test_client.get("/suppliers?is_active=true", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert "items" in response.json()

    def test_list_suppliers_customer_forbidden(self, test_client, customer_headers):
        """Test customer user cannot list suppliers."""
        response = test_client.get("/suppliers", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_supplier_business_success(self, test_client, business_headers):
        """Test retrieving supplier by ID."""
        sup_res = test_client.post("/suppliers", json={"name": f"Get Sup {uuid4().hex[:6]}"}, headers=business_headers)
        sup_id = sup_res.json()["id"]

        response = test_client.get(f"/suppliers/{sup_id}", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["id"] == sup_id

    def test_get_supplier_customer_forbidden(self, test_client, business_headers, customer_headers):
        """Test customer user cannot retrieve supplier details."""
        sup_res = test_client.post("/suppliers", json={"name": f"Sup {uuid4().hex[:6]}"}, headers=business_headers)
        sup_id = sup_res.json()["id"]

        response = test_client.get(f"/suppliers/{sup_id}", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_supplier_not_found(self, test_client, business_headers):
        """Test getting non-existent supplier returns 404."""
        response = test_client.get(f"/suppliers/{uuid4()}", headers=business_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_supplier_business_success(self, test_client, business_headers):
        """Test updating a supplier."""
        sup_res = test_client.post("/suppliers", json={"name": f"Old Sup {uuid4().hex[:6]}"}, headers=business_headers)
        sup_id = sup_res.json()["id"]

        update_payload = {"name": "Updated Supplier Name", "contact_person": "New Contact"}
        response = test_client.put(f"/suppliers/{sup_id}", json=update_payload, headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["name"] == "Updated Supplier Name"

    def test_update_supplier_customer_forbidden(self, test_client, business_headers, customer_headers):
        """Test customer user cannot update a supplier."""
        sup_res = test_client.post("/suppliers", json={"name": f"Sup {uuid4().hex[:6]}"}, headers=business_headers)
        sup_id = sup_res.json()["id"]

        response = test_client.put(f"/suppliers/{sup_id}", json={"name": "New Name"}, headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_supplier_not_found(self, test_client, business_headers):
        """Test updating non-existent supplier returns 404."""
        response = test_client.put(f"/suppliers/{uuid4()}", json={"name": "New Name"}, headers=business_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_deactivate_supplier_business_success(self, test_client, business_headers):
        """Test deactivating a supplier."""
        sup_res = test_client.post("/suppliers", json={"name": f"Deact Sup {uuid4().hex[:6]}"}, headers=business_headers)
        sup_id = sup_res.json()["id"]

        response = test_client.patch(f"/suppliers/{sup_id}/deactivate", headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["is_active"] is False

    def test_deactivate_supplier_customer_forbidden(self, test_client, business_headers, customer_headers):
        """Test customer user cannot deactivate a supplier."""
        sup_res = test_client.post("/suppliers", json={"name": f"Sup {uuid4().hex[:6]}"}, headers=business_headers)
        sup_id = sup_res.json()["id"]

        response = test_client.patch(f"/suppliers/{sup_id}/deactivate", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_deactivate_supplier_not_found(self, test_client, business_headers):
        """Test deactivating non-existent supplier returns 404."""
        response = test_client.patch(f"/suppliers/{uuid4()}/deactivate", headers=business_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

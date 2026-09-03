import pytest
from fastapi import status, HTTPException
from uuid import uuid4, UUID
from app.models.users import User
from app.models.category import Category
from app.models.product import Product


@pytest.fixture(autouse=True)
def mock_supabase_token_verifier(monkeypatch):
    """
    Dynamically resolve any token in format 'token_<user_id>' to user_id.
    """
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


class TestCategoryEndpoints:
    """Test endpoints in app/routers/category.py."""

    def test_create_category_business_success(self, test_client, business_headers):
        """Test business user can create a category."""
        payload = {
            "name": f"Test Category {uuid4().hex[:6]}",
            "description": "Category description",
            "is_active": True,
        }
        response = test_client.post("/categories", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_201_CREATED, response.text
        data = response.json()
        assert data["name"] == payload["name"]
        assert "id" in data
        assert "created_at" in data

    def test_create_category_customer_forbidden(self, test_client, customer_headers):
        """Test customer user cannot create a category."""
        payload = {"name": "Forbidden Category"}
        response = test_client.post("/categories", json=payload, headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_category_unauthorized(self, test_client):
        """Test unauthenticated user cannot create a category."""
        payload = {"name": "No Auth Category"}
        response = test_client.post("/categories", json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_category_validation_error(self, test_client, business_headers):
        """Test creating category with invalid data fails validation."""
        payload = {"name": ""}  # empty name
        response = test_client.post("/categories", json=payload, headers=business_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_categories_success(self, test_client, business_headers):
        """Test listing categories with pagination."""
        payload = {"name": f"List Cat {uuid4().hex[:6]}"}
        test_client.post("/categories", json=payload, headers=business_headers)

        response = test_client.get("/categories")
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_list_categories_filter_active(self, test_client, business_headers):
        """Test filtering categories by active status."""
        response = test_client.get("/categories?is_active=true")
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "items" in data

    def test_get_category_success(self, test_client, business_headers):
        """Test retrieving category by ID."""
        cat_res = test_client.post("/categories", json={"name": f"Get Cat {uuid4().hex[:6]}"}, headers=business_headers)
        cat_id = cat_res.json()["id"]

        response = test_client.get(f"/categories/{cat_id}")
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["id"] == cat_id

    def test_get_category_not_found(self, test_client):
        """Test retrieving non-existent category returns 404."""
        random_id = uuid4()
        response = test_client.get(f"/categories/{random_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_category_business_success(self, test_client, business_headers):
        """Test business user can update a category."""
        cat_res = test_client.post("/categories", json={"name": f"Old Name {uuid4().hex[:6]}"}, headers=business_headers)
        cat_id = cat_res.json()["id"]

        update_payload = {"name": f"New Name {uuid4().hex[:6]}", "description": "Updated desc"}
        response = test_client.put(f"/categories/{cat_id}", json=update_payload, headers=business_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["name"] == update_payload["name"]

    def test_update_category_customer_forbidden(self, test_client, business_headers, customer_headers):
        """Test customer user cannot update a category."""
        cat_res = test_client.post("/categories", json={"name": f"Cat {uuid4().hex[:6]}"}, headers=business_headers)
        assert cat_res.status_code == status.HTTP_201_CREATED, cat_res.text
        cat_id = cat_res.json()["id"]

        response = test_client.put(f"/categories/{cat_id}", json={"name": "New Name"}, headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_category_not_found(self, test_client, business_headers):
        """Test updating non-existent category returns 404."""
        random_id = uuid4()
        response = test_client.put(f"/categories/{random_id}", json={"name": "New Name"}, headers=business_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_category_slug_conflict(self, test_client, business_headers):
        """Test updating a category slug to an existing slug returns 409 conflict."""
        cat1 = test_client.post("/categories", json={"name": f"Cat One {uuid4().hex[:6]}"}, headers=business_headers).json()
        cat2 = test_client.post("/categories", json={"name": f"Cat Two {uuid4().hex[:6]}"}, headers=business_headers).json()

        # Update cat1 slug explicitly to 'cat-one-custom'
        test_client.put(f"/categories/{cat1['id']}", json={"slug": "cat-one-custom"}, headers=business_headers)

        # Try setting cat2's slug to 'cat-one-custom'
        response = test_client.put(f"/categories/{cat2['id']}", json={"slug": "cat-one-custom"}, headers=business_headers)
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_delete_category_business_success(self, test_client, business_headers):
        """Test deleting a category."""
        cat_res = test_client.post("/categories", json={"name": f"Delete Cat {uuid4().hex[:6]}"}, headers=business_headers)
        cat_id = cat_res.json()["id"]

        response = test_client.delete(f"/categories/{cat_id}", headers=business_headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Confirm category is gone
        get_res = test_client.get(f"/categories/{cat_id}")
        assert get_res.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_category_customer_forbidden(self, test_client, business_headers, customer_headers):
        """Test customer user cannot delete a category."""
        cat_res = test_client.post("/categories", json={"name": f"Cat {uuid4().hex[:6]}"}, headers=business_headers)
        assert cat_res.status_code == status.HTTP_201_CREATED, cat_res.text
        cat_id = cat_res.json()["id"]

        response = test_client.delete(f"/categories/{cat_id}", headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_category_not_found(self, test_client, business_headers):
        """Test deleting non-existent category returns 404."""
        random_id = uuid4()
        response = test_client.delete(f"/categories/{random_id}", headers=business_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_category_with_products_bad_request(self, test_client, business_headers, db_session, custom_business_user):
        """Test cannot delete category that has products attached."""
        cat_res = test_client.post("/categories", json={"name": f"Cat With Prods {uuid4().hex[:6]}"}, headers=business_headers)
        cat_id = UUID(cat_res.json()["id"])

        # Add a product directly to DB linked to this category
        prod = Product(
            id=uuid4(),
            name="Linked Product",
            sku=f"LINK-{uuid4().hex[:6]}",
            price=10.00,
            cost=5.00,
            category_id=cat_id,
            created_by=custom_business_user.id,
        )
        db_session.add(prod)
        db_session.commit()

        response = test_client.delete(f"/categories/{cat_id}", headers=business_headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

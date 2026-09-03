import pytest
from fastapi import status, HTTPException
from uuid import uuid4
from app.models.users import User


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
    """Create a local test customer in db_session."""
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
def customer_headers(custom_customer_user):
    return {"Authorization": f"Bearer token_{custom_customer_user.id}"}


class TestUserEndpoints:
    """Test endpoints in app/routers/user.py."""

    def test_get_profile_success(self, test_client, customer_headers, custom_customer_user):
        """Test getting current user profile."""
        response = test_client.get("/users/profile", headers=customer_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert data["id"] == str(custom_customer_user.id)
        assert data["email"] == custom_customer_user.email
        assert data["username"] == custom_customer_user.username
        assert data["role"] == "CUSTOMER"

    def test_get_profile_unauthorized(self, test_client):
        """Test getting profile without auth header fails."""
        response = test_client.get("/users/profile")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_profile_put_success(self, test_client, customer_headers, custom_customer_user):
        """Test updating profile with PUT (updates name and phone_number)."""
        payload = {
            "first_name": "UpdatedJohn",
            "last_name": "UpdatedDoe",
            "phone_number": "03001234567",
        }
        response = test_client.put(
            "/users/profile",
            json=payload,
            headers=customer_headers,
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert data["name"] == "UpdatedJohnUpdatedDoe"
        assert data["phone_number"] == "03001234567"

    def test_update_profile_put_validation_error(self, test_client, customer_headers):
        """Test updating profile with invalid phone number fails validation."""
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "phone_number": "12345",  # Invalid phone
        }
        response = test_client.put(
            "/users/profile",
            json=payload,
            headers=customer_headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_patch_profile_success(self, test_client, customer_headers):
        """Test partial profile update with PATCH."""
        payload = {
            "phone_number": "03119876543",
        }
        response = test_client.patch(
            "/users/profile",
            json=payload,
            headers=customer_headers,
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert data["phone_number"] == "03119876543"

    def test_patch_profile_invalid_phone(self, test_client, customer_headers):
        """Test PATCH with invalid phone number format."""
        payload = {
            "phone_number": "invalid_phone",
        }
        response = test_client.patch(
            "/users/profile",
            json=payload,
            headers=customer_headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_active_sessions_success(self, test_client, customer_headers):
        """Test retrieving active sessions for user."""
        response = test_client.get("/users/sessions", headers=customer_headers)
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert "total_active_sessions" in data
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_get_active_sessions_unauthorized(self, test_client):
        """Test retrieving active sessions without token fails."""
        response = test_client.get("/users/sessions")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_account_success(self, test_client, customer_headers, monkeypatch):
        """Test deleting user profile."""
        monkeypatch.setattr("app.routers.user.supabase_service.auth.admin.delete_user", lambda uid: None)

        response = test_client.delete("/users/profile", headers=customer_headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_res = test_client.get("/users/profile", headers=customer_headers)
        assert get_res.status_code == status.HTTP_401_UNAUTHORIZED

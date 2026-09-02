import pytest
from uuid import uuid4
from fastapi import status


class TestAuthentication:
    """Test authentication endpoints."""

    # ========================================================
    # SIGNUP
    # ========================================================

    @pytest.mark.auth
    def test_customer_signup(
        self,
        test_client,
        test_customer_data,
    ):
        """Test customer user registration."""

        response = test_client.post(
            "/auth/signup",
            json=test_customer_data,
        )

        assert response.status_code == status.HTTP_201_CREATED, (
            f"Signup failed: {response.status_code} - {response.text}"
        )

        data = response.json()

        assert data["email"] == test_customer_data["email"]
        assert data["role"] == "CUSTOMER"
        assert data["username"] == test_customer_data["username"]

    @pytest.mark.auth
    def test_business_signup(
        self,
        test_client,
        test_business_data,
    ):
        """Test business user registration."""

        response = test_client.post(
            "/auth/signup",
            json=test_business_data,
        )

        assert response.status_code == status.HTTP_201_CREATED, (
            f"Signup failed: {response.status_code} - {response.text}"
        )

        data = response.json()

        assert data["email"] == test_business_data["email"]
        assert data["role"] == "BUSINESS"
        assert data["username"] == test_business_data["username"]


    # ========================================================
    # LOGIN
    # ========================================================

    @pytest.mark.auth
    def test_login_success(
        self,
        test_client,
        test_customer_data,
    ):
        """Test successful login."""

        # Signup
        signup_response = test_client.post(
            "/auth/signup",
            json=test_customer_data,
        )

        assert signup_response.status_code == status.HTTP_201_CREATED, (
            f"Signup failed: "
            f"{signup_response.status_code} - "
            f"{signup_response.text}"
        )

        # Login
        response = test_client.post(
            "/auth/login",
            json={
                "email": test_customer_data["email"],
                "password": test_customer_data["password"],
            },
        )

        assert response.status_code == status.HTTP_200_OK, (
            f"Login failed: "
            f"{response.status_code} - "
            f"{response.text}"
        )

        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.auth
    def test_login_wrong_password(
        self,
        test_client,
        test_customer_data,
    ):
        """Test login fails with wrong password."""

        # Signup
        signup_response = test_client.post(
            "/auth/signup",
            json=test_customer_data,
        )

        assert signup_response.status_code == status.HTTP_201_CREATED, (
            f"Signup failed: "
            f"{signup_response.status_code} - "
            f"{signup_response.text}"
        )

        # Login with wrong password
        response = test_client.post(
            "/auth/login",
            json={
                "email": test_customer_data["email"],
                "password": "WrongPassword123!",
            },
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, (
            f"Expected 401, got {response.status_code}: {response.text}"
        )

        assert "Invalid credentials" in response.json()["message"]

    # ========================================================
    # PROFILE
    # ========================================================

    @pytest.mark.auth
    def test_get_profile(
        self,
        test_client,
        customer_auth_headers,
    ):
        """Test get user profile."""

        response = test_client.get(
            "/users/profile",
            headers=customer_auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK, (
            f"Profile request failed: "
            f"{response.status_code} - "
            f"{response.text}"
        )

        data = response.json()

        assert "email" in data
        assert "username" in data
        assert data["role"] == "CUSTOMER"

    @pytest.mark.auth
    def test_profile_without_auth(
        self,
        test_client,
    ):
        """Test cannot access profile without authentication."""

        response = test_client.get(
            "/users/profile"
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED,(
            f"Expected 401, got "
            f"{response.status_code}: {response.text}"
        )
        
    @pytest.mark.auth
    def test_invalid_token(
        self,
        test_client,
    ):
        """Test invalid token is rejected."""

        response = test_client.get(
            "/users/profile",
            headers={
                "Authorization": "Bearer invalid_token_xyz"
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, (
            f"Expected 401, got "
            f"{response.status_code}: {response.text}"
        )


# ============================================================
# REGISTRATION VALIDATION
# ============================================================

class TestRegistrationValidation:
    """Test signup validation rules."""

    @pytest.mark.auth
    def test_password_too_short(
        self,
        test_client,
        test_customer_data,
    ):
        """Test password must be at least 8 characters."""

        data = test_customer_data.copy()
        data["password"] = "Short1!"

        response = test_client.post(
            "/auth/signup",
            json=data,
        )

        assert response.status_code == (
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    @pytest.mark.auth
    def test_password_missing_number(
        self,
        test_client,
        test_customer_data,
    ):
        """Test password must contain a number."""

        data = test_customer_data.copy()
        data["password"] = "NoNumbers!"

        response = test_client.post(
            "/auth/signup",
            json=data,
        )

        assert response.status_code == (
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    @pytest.mark.auth
    def test_password_missing_special_char(
        self,
        test_client,
        test_customer_data,
    ):
        """Test password must contain a special character."""

        data = test_customer_data.copy()
        data["password"] = "NoSpecial123"

        response = test_client.post(
            "/auth/signup",
            json=data,
        )

        assert response.status_code == (
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    @pytest.mark.auth
    def test_invalid_role(
        self,
        test_client,
        test_customer_data,
    ):
        """Test invalid role is rejected."""

        data = test_customer_data.copy()
        data["role"] = "ADMIN"

        response = test_client.post(
            "/auth/signup",
            json=data,
        )

        assert response.status_code == (
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    @pytest.mark.auth
    def test_invalid_email(
        self,
        test_client,
        test_customer_data,
    ):
        """Test invalid email is rejected."""

        data = test_customer_data.copy()
        data["email"] = "not-an-email"

        response = test_client.post(
            "/auth/signup",
            json=data,
        )

        assert response.status_code == (
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )


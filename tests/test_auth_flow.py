import pytest
from fastapi import status, HTTPException
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from app.models.users import User
from app.models.sessions import UserSession
from app.core.security import hash_token


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
def customer_headers(custom_customer_user):
    return {"Authorization": f"Bearer token_{custom_customer_user.id}"}


class TestAuthFlowEndpoints:
    """Test auth endpoints: logout, logout-all-devices, refresh."""

    def test_logout_success(self, test_client, customer_headers, db_session, custom_customer_user):
        """Test authenticated logout revokes active user session."""
        session = UserSession(
            user_id=custom_customer_user.id,
            refresh_token_hash=hash_token("test_refresh_token_123"),
            user_agent="pytest",
            ip_address="127.0.0.1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(session)
        db_session.commit()

        response = test_client.post("/auth/logout", headers=customer_headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        db_session.refresh(session)
        assert session.revoked_at is not None

    def test_logout_unauthenticated(self, test_client):
        """Test logout without token returns 401."""
        response = test_client.post("/auth/logout")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_all_devices_success(self, test_client, customer_headers, db_session, custom_customer_user):
        """Test logout all devices revokes all sessions for user."""
        s1 = UserSession(
            user_id=custom_customer_user.id,
            refresh_token_hash=hash_token("token_device_1"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        s2 = UserSession(
            user_id=custom_customer_user.id,
            refresh_token_hash=hash_token("token_device_2"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add_all([s1, s2])
        db_session.commit()

        response = test_client.post("/auth/logout-all-devices", headers=customer_headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        db_session.refresh(s1)
        db_session.refresh(s2)
        assert s1.revoked_at is not None
        assert s2.revoked_at is not None

    def test_logout_all_devices_unauthenticated(self, test_client):
        """Test logout all devices without token returns 401."""
        response = test_client.post("/auth/logout-all-devices")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token_missing_header(self, test_client):
        """Test refresh token without Authorization header returns 401."""
        response = test_client.post("/auth/refresh")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token_invalid_token(self, test_client):
        """Test refresh token with unknown token returns 401."""
        response = test_client.post(
            "/auth/refresh",
            headers={"Authorization": "Bearer non_existent_token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token_revoked_token(self, test_client, db_session, custom_customer_user):
        """Test refresh token with revoked session returns 401."""
        raw_token = "revoked_refresh_token"
        session = UserSession(
            user_id=custom_customer_user.id,
            refresh_token_hash=hash_token(raw_token),
            revoked_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(session)
        db_session.commit()

        response = test_client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "revoked" in response.json()["message"].lower()

    def test_refresh_token_expired_token(self, test_client, db_session, custom_customer_user):
        """Test refresh token with expired session returns 401."""
        raw_token = "expired_refresh_token"
        session = UserSession(
            user_id=custom_customer_user.id,
            refresh_token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db_session.add(session)
        db_session.commit()

        response = test_client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "expired" in response.json()["message"].lower()

    def test_refresh_token_success(self, test_client, db_session, custom_customer_user, monkeypatch):
        """Test successful access token refresh."""
        raw_token = "valid_refresh_token_xyz"
        session = UserSession(
            user_id=custom_customer_user.id,
            refresh_token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(session)
        db_session.commit()

        class MockSession:
            access_token = "new_access_token_123"

        class MockResponse:
            session = MockSession()

        monkeypatch.setattr(
            "app.services.auth.supabase_service.auth.refresh_session",
            lambda refresh_token: MockResponse(),
        )

        response = test_client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert data["access_token"] == "new_access_token_123"
        assert data["token_type"] == "bearer"

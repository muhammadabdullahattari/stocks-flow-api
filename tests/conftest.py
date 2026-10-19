import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from uuid import uuid4
from app.core.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.users import User
from app.core.security import hash_password

@pytest.fixture(scope="session")
def test_db_engine():
    """
    Create a PostgreSQL engine specifically for testing.
    """

    engine = create_engine(
        settings.Test_DATABASE_URL,
        pool_pre_ping=True,
    )

    Base.metadata.create_all(bind=engine)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


MOCKED_SUPABASE_USERS = {}

@pytest.fixture(autouse=True)
def mock_supabase_auth_service(monkeypatch):
    """
    Mock Supabase Auth calls so test runs do not hit external network rate limits.
    """
    class MockUser:
        def __init__(self, user_id=None, email=None, user_metadata=None):
            self.id = user_id or str(uuid4())
            self.email = email
            self.user_metadata = user_metadata or {}

    class MockSession:
        def __init__(self, access_token, refresh_token):
            self.access_token = access_token
            self.refresh_token = refresh_token

    class MockAuthResponse:
        def __init__(self, user, session=None):
            self.user = user
            self.session = session

    def mock_admin_create_user(params):
        email = params.get("email")
        user_id = str(uuid4())
        MOCKED_SUPABASE_USERS[email] = user_id
        return MockAuthResponse(user=MockUser(user_id=user_id, email=email, user_metadata=params.get("user_metadata")))

    def mock_sign_in_with_password(credentials):
        email = credentials.get("email")
        password = credentials.get("password")
        if password == "WrongPassword123!":
            raise Exception("Invalid login credentials")
        user_id = MOCKED_SUPABASE_USERS.get(email, str(uuid4()))
        session = MockSession(access_token=f"token_{user_id}", refresh_token=f"refresh_{uuid4().hex}")
        return MockAuthResponse(user=MockUser(user_id=user_id, email=email), session=session)

    def mock_get_user(token):
        if token and token.startswith("token_"):
            user_id = token.replace("token_", "")
        else:
            user_id = str(uuid4())
        return MockAuthResponse(user=MockUser(user_id=user_id))

    def mock_refresh_session(token):
        user_id = str(uuid4())
        session = MockSession(access_token=f"token_{user_id}", refresh_token=f"new_refresh_{uuid4().hex}")
        return MockAuthResponse(user=MockUser(user_id=user_id), session=session)

    try:
        monkeypatch.setattr("app.core.supabase_client.supabase_service.auth.admin.create_user", mock_admin_create_user)
        monkeypatch.setattr("app.core.supabase_client.supabase_service.auth.sign_in_with_password", mock_sign_in_with_password)
        monkeypatch.setattr("app.core.supabase_client.supabase.auth.get_user", mock_get_user)
        monkeypatch.setattr("app.core.supabase_client.supabase_service.auth.refresh_session", mock_refresh_session)
    except Exception:
        pass


@pytest.fixture(scope="function")
def db_session(test_db_engine):
    """
    Create a fresh database transaction for each test.

    All database changes made during the test are rolled back
    after the test finishes.
    """

    connection = test_db_engine.connect()
    transaction = connection.begin()

    TestingSessionLocal = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
    )

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

@pytest.fixture(scope="function")
def test_client(db_session):
    """
    Override FastAPI's normal database dependency so tests
    use the PostgreSQL test database.
    """

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)

    yield client

    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_supabase_token_verifier(monkeypatch):
    """Dynamically resolve any token in format 'token_<user_id>' to user_id."""
    from fastapi import HTTPException, status
    def mock_verify_supabase_token(token: str) -> dict:
        if token == "invalid_token" or not token or not token.startswith("token_"):
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
def test_customer_data():
    """
    Generate unique customer credentials for every test.
    """
    unique = uuid4().hex[:8]

    return {
        "first_name": "John",
        "last_name": "Customer",
        "username": f"johncustomer_{unique}",
        "email": f"john.customer_{unique}@example.com",
        "password": "TestPass123!",
        "role": "CUSTOMER",
    }


@pytest.fixture
def test_business_data():
    """
    Generate unique business credentials for every test.
    """

    unique = uuid4().hex[:8]

    return {
        "first_name": "Acme",
        "last_name": "Corp",
        "username": f"acmecorp_{unique}",
        "email": f"acme_{unique}@business.com",
        "password": "BizPass123!",
        "role": "BUSINESS",
    }

@pytest.fixture
def test_customer_user(db_session, test_customer_data):
    """
    Create a local test customer directly in PostgreSQL.
    """

    user = User(
        id=uuid4(),
        username=test_customer_data["username"],
        name=(
            f"{test_customer_data['first_name']} "
            f"{test_customer_data['last_name']}"
        ),
        email=test_customer_data["email"],
        hashed_password=hash_password(
            test_customer_data["password"]
        ),
        role="CUSTOMER",
        is_active=True,
        is_verified=False,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def test_business_user(db_session, test_business_data):
    """
    Create a local test business directly in PostgreSQL.
    """

    user = User(
        id=uuid4(),
        username=test_business_data["username"],
        name=(
            f"{test_business_data['first_name']} "
            f"{test_business_data['last_name']}"
        ),
        email=test_business_data["email"],
        hashed_password=hash_password(
            test_business_data["password"]
        ),
        role="BUSINESS",
        is_active=True,
        is_verified=False,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def customer_auth_headers(test_client, test_customer_data):
    """
    Signup a customer and obtain an access token.

    Requires Supabase email confirmation to be disabled
    for the test Supabase project.
    """

    signup_response = test_client.post(
        "/auth/signup",
        json=test_customer_data,
    )

    assert signup_response.status_code == 201, (
        f"Signup failed: "
        f"{signup_response.status_code} - "
        f"{signup_response.text}"
    )

    login_response = test_client.post(
        "/auth/login",
        json={
            "email": test_customer_data["email"],
            "password": test_customer_data["password"],
        },
    )

    assert login_response.status_code == 200, (
        f"Login failed: "
        f"{login_response.status_code} - "
        f"{login_response.text}"
    )

    tokens = login_response.json()

    assert "access_token" in tokens, (
        f"access_token missing: {tokens}"
    )

    return {
        "Authorization": f"Bearer {tokens['access_token']}"
    }


@pytest.fixture
def business_auth_headers(test_client, test_business_data):
    """
    Signup a business and obtain an access token.

    Requires Supabase email confirmation to be disabled
    for the test Supabase project.
    """

    signup_response = test_client.post(
        "/auth/signup",
        json=test_business_data,
    )

    assert signup_response.status_code == 201, (
        f"Signup failed: "
        f"{signup_response.status_code} - "
        f"{signup_response.text}"
    )

    login_response = test_client.post(
        "/auth/login",
        json={
            "email": test_business_data["email"],
            "password": test_business_data["password"],
        },
    )

    assert login_response.status_code == 200, (
        f"Login failed: "
        f"{login_response.status_code} - "
        f"{login_response.text}"
    )

    tokens = login_response.json()

    assert "access_token" in tokens, (
        f"access_token missing: {tokens}"
    )

    return {
        "Authorization": f"Bearer {tokens['access_token']}"
    }

@pytest.fixture
def create_category(test_client, business_auth_headers):

    def _create_category(
        name="Test Category",
        slug=None,
        description=None,
        is_active=True,
    ):
        """
        Create a category for product-related tests.

        A unique slug is generated by default so repeated
        tests do not conflict with database unique constraints.
        """

        if slug is None:
            slug = f"test-category-{uuid4().hex[:8]}"

        response = test_client.post(
            "/categories",
            json={
                "name": name,
                "slug": slug,
                "description": description,
                "is_active": is_active,
            },
            headers=business_auth_headers,
        )

        assert response.status_code == 201, (
            f"Category creation failed: "
            f"{response.status_code} - "
            f"{response.text}"
        )

        return response.json()

    return _create_category

@pytest.fixture
def create_product(
    test_client,
    business_auth_headers,
    create_category,
):

    category = create_category()

    def _create_product(
        name="Test Product",
        sku=None,
        price=99.99,
        cost=50.00,
        description=None,
        status="active",
    ):
        """
        Create a product for tests.

        A unique SKU is generated by default.
        """

        if sku is None:
            sku = f"TEST-SKU-{uuid4().hex[:8]}"

        response = test_client.post(
            "/products",
            json={
                "name": name,
                "sku": sku,
                "price": float(price),
                "cost": float(cost),
                "description": description,
                "category_id": category["id"],
                "status": status,
                "is_active": True,
            },
            headers=business_auth_headers,
        )

        assert response.status_code == 201, (
            f"Product creation failed: "
            f"{response.status_code} - "
            f"{response.text}"
        )

        return response.json()

    return _create_product

@pytest.fixture
def create_supplier(test_client, business_auth_headers):

    def _create_supplier(
        name=None,
        email=None,
        phone=None,
        contact_person=None,
        is_active=True,
    ):
        """
        Create a supplier for tests.
        """

        if name is None:
            name = f"Test Supplier {uuid4().hex[:8]}"

        if email is None:
            email = f"supplier_{uuid4().hex[:8]}@example.com"

        response = test_client.post(
            "/suppliers",
            json={
                "name": name,
                "email": email,
                "phone": phone,
                "contact_person": contact_person,
                "is_active": is_active,
            },
            headers=business_auth_headers,
        )

        assert response.status_code == 201, (
            f"Supplier creation failed: "
            f"{response.status_code} - "
            f"{response.text}"
        )

        return response.json()

    return _create_supplier

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "auth: authentication tests"
    )

    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow"
    )

    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests"
    )


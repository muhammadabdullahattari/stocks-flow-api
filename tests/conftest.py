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

@pytest.fixture
def test_customer_data():
    """
    Generate unique customer credentials for every test.

    This prevents Supabase Auth users from conflicting when
    pytest is executed multiple times.
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


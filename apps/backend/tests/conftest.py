import pytest
from app.core.config import settings

@pytest.fixture(scope="session", autouse=True)
def configure_test_settings():
    """Configure settings for the test runner session to ensure compatibility with legacy test user IDs."""
    settings.AUTH_MODE = "mock"
    settings.MOCK_USER_ID = "00000000-0000-0000-0000-000000000000"
    settings.APP_ENV = "development"
    settings.validate_auth_settings()

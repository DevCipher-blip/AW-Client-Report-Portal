import pytest

from portal import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE_PATH": str(tmp_path / "portal.db")})


@pytest.fixture
def client(app):
    return app.test_client()

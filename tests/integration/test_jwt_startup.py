import os
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from backend.api.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def disable_dotenv(monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")


@pytest.mark.usefixtures("disable_dotenv")
@pytest.mark.parametrize("db_url", ["sqlite:///:memory:", "postgresql+psycopg2:///"])
@pytest.mark.parametrize(
    "secret",
    [None, "", "test-only-secret-do-not-use-in-production", "some_awesome_key"],
    ids=["missing", "empty", "former-fallback", "former-example"],
)
@pytest.mark.anyio
async def test_invalid_jwt_key_stops_startup(db_url, secret, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", db_url)
    if secret is None:
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("JWT_SECRET_KEY", secret)

    with patch(
        "backend.composition._infrastructure.get_engine",
        side_effect=AssertionError("Database setup started before JWT key validation"),
    ) as get_engine:
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY") as error:
            async with app.router.lifespan_context(app):
                pytest.fail("Application started with invalid JWT configuration")
        get_engine.assert_not_called()

    if secret:
        assert secret not in str(error.value)


@pytest.fixture(params=["sqlite", "postgresql"])
def startup_database(request, tmp_path, monkeypatch):
    if request.param == "sqlite":
        yield f"sqlite:///{tmp_path / 'jwt-startup.sqlite'}"
        return

    url = os.environ.get("TEST_PERSONAL_CATEGORIES_POSTGRES_URL")
    if not url:
        pytest.skip("Requires a PostgreSQL test database")
    engine = create_engine(url)
    schema = f"jwt_startup_{uuid4().hex}"
    try:
        with engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
        monkeypatch.setenv("PGOPTIONS", f"-c search_path={schema}")
        try:
            yield url
        finally:
            with engine.begin() as connection:
                connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    finally:
        engine.dispose()


@pytest.mark.usefixtures("disable_dotenv")
@pytest.mark.anyio
async def test_explicit_jwt_key_allows_startup(startup_database, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", startup_database)
    monkeypatch.setenv("JWT_SECRET_KEY", "jwt-startup-test-key-at-least-32-bytes")
    async with app.router.lifespan_context(app):
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                assert (await client.get("/openapi.json")).status_code == 200
        finally:
            app.state.container._session.close()
            app.state.container._engine.dispose()

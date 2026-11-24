from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from backend.domain.value_objects.types import UserId
from backend.infrastructure.database.connection import apply_schema

_SEED_SQL = [
    "INSERT OR IGNORE INTO units (name, unit_group) VALUES ('g',    'weight')",
    "INSERT OR IGNORE INTO units (name, unit_group) VALUES ('kg',   'weight')",
    "INSERT OR IGNORE INTO units (name, unit_group) VALUES ('ml',   'volume')",
    "INSERT OR IGNORE INTO units (name, unit_group) VALUES ('l',    'volume')",
    "INSERT OR IGNORE INTO units (name, unit_group) VALUES ('pcs',  'count_pcs')",
    "INSERT OR IGNORE INTO units (name, unit_group) VALUES ('box',  'count_box')",
    "INSERT OR IGNORE INTO units (name, unit_group) VALUES ('pack', 'count_pack')",
    "INSERT OR IGNORE INTO units (name, unit_group) VALUES ('serv', 'servings')",
    "INSERT OR IGNORE INTO recipe_categories  (user_id, name, active) VALUES (1, 'Завтраки', 1)",
    "INSERT OR IGNORE INTO recipe_categories  (user_id, name, active) VALUES (1, 'Основные', 1)",
    "INSERT OR IGNORE INTO recipe_categories  (user_id, name, active) VALUES (1, 'Салаты',   1)",
    "INSERT OR IGNORE INTO product_categories (user_id, name, active) VALUES (1, 'Сыпучие',  1)",
    "INSERT OR IGNORE INTO product_categories (user_id, name, active) VALUES (1, 'Молочные', 1)",
    "INSERT OR IGNORE INTO product_categories (user_id, name, active) VALUES (1, 'Мясо',     1)",
]

_SEED_USER_SQL = (
    "INSERT INTO users (email, nickname, hashed_password, created_at) "
    "VALUES ('test@example.com', 'tester', 'hashed', '2025-01-01 00:00:00')"
)

# Three system meal types for user_id=1 (ids 1=Завтрак, 2=Обед, 3=Ужин)
_SEED_MEAL_TYPES_SQL = [
    "INSERT OR IGNORE INTO meal_types (id, user_id, name, time, is_system, sort_order) VALUES (1, 1, 'Завтрак', '08:00', 1, 0)",
    "INSERT OR IGNORE INTO meal_types (id, user_id, name, time, is_system, sort_order) VALUES (2, 1, 'Обед', '13:00', 1, 1)",
    "INSERT OR IGNORE INTO meal_types (id, user_id, name, time, is_system, sort_order) VALUES (3, 1, 'Ужин', '18:00', 1, 2)",
]

TEST_USER_ID = UserId(1)


@pytest.fixture
def conn() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys = ON")

    apply_schema(engine)
    session = Session(engine)
    session.execute(text(_SEED_USER_SQL))
    for stmt in _SEED_SQL:
        session.execute(text(stmt))
    for stmt in _SEED_MEAL_TYPES_SQL:
        session.execute(text(stmt))
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def user_id() -> UserId:
    return TEST_USER_ID


@pytest.fixture
def isolation_client(tmp_path, monkeypatch):
    """Real app, schema, FK enforcement, registration and JWT authentication."""
    from fastapi.testclient import TestClient

    from backend.api.main import app

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'isolation.sqlite'}")
    monkeypatch.setenv("JWT_SECRET_KEY", "isolation-test-secret-key-at-least-32-bytes")
    with TestClient(app) as client:
        with app.state.database.engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        yield client


@pytest.fixture
def isolation_users(isolation_client):
    """Reusable two-user API data for TASK 1–3; no assumed category IDs."""
    from tests.integration.api_isolation_helpers import request_ok

    client = isolation_client
    users = []
    for name in ("alice", "bob"):
        email = f"{name}@example.com"
        user = request_ok(
            client,
            "POST",
            "auth/register",
            {},
            {"email": email, "nickname": name, "password": "Password123!"},
            201,
        )
        pair = request_ok(
            client,
            "POST",
            "auth/login",
            {},
            {"email": email, "password": "Password123!"},
        )
        users.append(
            dict(
                user,
                headers={"Authorization": f"Bearer {pair['access_token']}"},
                objects={},
                bodies={},
            )
        )
    for user, other in ((users[0], users[1]), (users[1], users[0])):
        headers = user["headers"]
        pc = request_ok(client, "GET", "product-categories", headers)[0]["id"]
        rc = request_ok(client, "GET", "recipe-categories", headers)[0]["id"]
        bodies = {
            "products": {
                "name": "Private product",
                "category_id": pc,
                "recipe_unit": "g",
                "purchase_unit": "kg",
                "price_amount": "80",
                "conversion_factor": 1000,
            },
            "recipes": {"name": "Private recipe", "category_id": rc, "servings": 2},
            "menus": {"name": "Private menu"},
            "preferences": {
                "name": "Private preference",
                "type": "ALLERGY",
                "mode": "BLOCKED",
            },
            "family-members": {"name": "Private member"},
            "meal-types": {"name": "Private meal", "time": "10:00"},
        }
        for kind, body in bodies.items():
            body["name"] = f"{user['nickname']} {body['name']}"
            if kind == "family-members":
                body["preference_ids"] = [user["objects"]["preferences"]["id"]]
            user["objects"][kind] = request_ok(
                client, "POST", kind, headers, dict(body, user_id=other["id"]), 201
            )
        saved = request_ok(
            client, "POST", "shopping-lists", headers, {"user_id": other["id"]}, 201
        )
        bodies["shopping-lists"] = {
            "name": "Private shopping",
            "items": [
                {
                    "product_name": "Private item",
                    "category": "Other",
                    "quantity_amount": 1,
                    "quantity_unit": "g",
                    "buy_quantity_amount": 1,
                    "buy_quantity_unit": "g",
                    "cost_amount": 1,
                }
            ],
        }
        user["objects"]["shopping-lists"] = request_ok(
            client,
            "PUT",
            f"shopping-lists/{saved['id']}",
            headers,
            bodies["shopping-lists"],
        )
        user["bodies"] = bodies
    return client, users


@pytest.fixture
def second_owner(conn):
    from backend.domain.entities.user import User
    from backend.infrastructure.repositories.orm_user_repository import OrmUserRepository

    return OrmUserRepository(conn).save(
        User(UserId(0), "second@example.com", "other", "hash")
    ).id

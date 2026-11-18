import asyncio
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from backend.api.main import app
from backend.infrastructure.database.connection import apply_schema, get_engine


def run_lifespan(messages):
    async def receive():
        return next(events)

    async def send(message):
        messages.append(message)

    events = iter([{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}])
    asyncio.run(app({"type": "lifespan"}, receive, send))


@pytest.fixture(params=["sqlite", "postgresql"])
def migration_database(request, tmp_path, monkeypatch):
    admin = None
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path / 'migration.sqlite'}"
    else:
        url = os.environ.get("TEST_PERSONAL_CATEGORIES_POSTGRES_URL")
        if not url:
            pytest.skip("Requires a PostgreSQL test database")
        admin = create_engine(url)
        schema = f"test_categories_{uuid4().hex}"
        with admin.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
        monkeypatch.setenv("PGOPTIONS", f"-c search_path={schema}")
    monkeypatch.setenv("DATABASE_URL", url)
    engine = get_engine(url)
    try:
        yield engine, Config("alembic.ini")
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
            admin.dispose()


def test_empty_database(migration_database, monkeypatch):
    engine, config = migration_database
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret")
    head = ScriptDirectory.from_config(config).get_current_head()

    for _ in range(2):
        messages = []
        run_lifespan(messages)
        assert [message["type"] for message in messages] == [
            "lifespan.startup.complete",
            "lifespan.shutdown.complete",
        ]
        with engine.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == head
            )
            units = (
                conn.execute(text("SELECT name FROM units ORDER BY name"))
                .scalars()
                .all()
            )
            assert units == [
                "box",
                "g",
                "kg",
                "l",
                "ml",
                "pack",
                "pcs",
                "serv",
                "tbsp",
                "tsp",
            ]
    command.upgrade(config, "head")

    for table in ("product_categories", "recipe_categories"):
        columns = {c["name"]: c for c in inspect(engine).get_columns(table)}
        assert columns["user_id"]["nullable"] is False
        with engine.connect() as conn:
            assert conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() == 0


def test_startup_rejects_unversioned_database(migration_database, monkeypatch):
    engine, _ = migration_database
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE legacy_data (value INTEGER)"))
        conn.execute(text("INSERT INTO legacy_data VALUES (42)"))

    messages = []
    with pytest.raises(RuntimeError, match="отсутствует ревизия Alembic"):
        run_lifespan(messages)
    assert [message["type"] for message in messages] == ["lifespan.startup.failed"]

    assert inspect(engine).get_table_names() == ["legacy_data"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT value FROM legacy_data")).scalar_one() == 42


@pytest.mark.parametrize("upgrade", ["alembic", "startup"])
def test_migrate_personal_category_catalog(migration_database, upgrade, monkeypatch):
    engine, config = migration_database
    command.upgrade(config, "c2d3e4f5a6b7")
    with engine.begin() as conn:
        for owner in (1, 2, 3):
            conn.execute(
                text(
                    "INSERT INTO users (id,email,hashed_password,created_at) VALUES (:id,:email,'hash','2026-01-01')"
                ),
                {"id": owner, "email": f"{owner}@test.example"},
            )
        conn.execute(text("INSERT INTO units (name,unit_group) VALUES ('g','weight')"))
        for kind in ("product", "recipe"):
            conn.execute(
                text(
                    f"INSERT INTO {kind}_categories (id,name,active,color) VALUES (50,'Shared',1,NULL),(51,'Inactive',0,'#ABCDEF')"
                )
            )
        for owner in (1, 2):
            for stmt in (
                "INSERT INTO products (id,user_id,name,category_id,recipe_unit,purchase_unit) VALUES (:id,:id,'Product',50,'g','g')",
                "INSERT INTO recipes (id,user_id,name,category_id) VALUES (:id,:id,'Recipe',50)",
                "INSERT INTO menus (id,user_id,name) VALUES (:id,:id,'Menu')",
                "INSERT INTO menu_slots (menu_id,day,meal_type,recipe_id) VALUES (:id,0,'Brunch',:id)",
                "INSERT INTO preferences (id,user_id,name,type,mode) VALUES (:id,:id,'Preference','CATEGORY_BASED','BLOCKED')",
                "INSERT INTO preference_categories (preference_id,category_id) VALUES (:id,51)",
                "INSERT INTO preference_recipe_categories (preference_id,recipe_category_id) VALUES (:id,50)",
                "INSERT INTO recipe_ingredients (recipe_id,product_id,amount,unit) VALUES (:id,:id,10,'g')",
            ):
                conn.execute(text(stmt), {"id": owner})

    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret")
    if upgrade == "alembic":
        command.upgrade(config, "head")
    else:
        run_lifespan([])
        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == (ScriptDirectory.from_config(config).get_current_head())
    run_lifespan([])
    command.upgrade(config, "head")
    with engine.connect() as conn:
        for kind in ("product", "recipe"):
            assert conn.execute(
                text(
                    f"SELECT user_id,name,active,color FROM {kind}_categories ORDER BY user_id,name"
                )
            ).all() == [
                (owner, name, active, color)
                for owner in (1, 2, 3)
                for name, active, color in (
                    ("Inactive", 0, "#ABCDEF"),
                    ("Shared", 1, None),
                )
            ]
            assert conn.execute(
                text(
                    f"SELECT obj.id,cat.user_id,cat.name FROM {kind}s obj JOIN {kind}_categories cat ON obj.category_id=cat.id ORDER BY obj.id"
                )
            ).all() == [(1, 1, "Shared"), (2, 2, "Shared")]
        assert conn.execute(
            text(
                "SELECT p.id,pc.user_id,pc.name,rc.user_id,rc.name FROM preferences p JOIN preference_categories l ON l.preference_id=p.id JOIN product_categories pc ON pc.id=l.category_id JOIN preference_recipe_categories r ON r.preference_id=p.id JOIN recipe_categories rc ON rc.id=r.recipe_category_id ORDER BY p.id"
            )
        ).all() == [(1, 1, "Inactive", 1, "Shared"), (2, 2, "Inactive", 2, "Shared")]
        assert conn.execute(
            text(
                "SELECT recipe_id,product_id FROM recipe_ingredients ORDER BY recipe_id"
            )
        ).all() == [(1, 1), (2, 2)]
        assert conn.execute(
            text(
                "SELECT ms.menu_id,ms.recipe_id,mt.user_id,mt.name,mt.is_system "
                "FROM menu_slots ms JOIN meal_types mt ON mt.id=ms.meal_type_id ORDER BY ms.menu_id"
            )
        ).all() == [(1, 1, 1, "Brunch", False), (2, 2, 2, "Brunch", False)]
        for table in ("product_categories", "recipe_categories"):
            conn.execute(
                text(f"INSERT INTO {table} (user_id,name) VALUES (3,'After upgrade')")
            )
        if engine.dialect.name == "sqlite":
            assert conn.execute(text("PRAGMA foreign_key_check")).all() == []


@pytest.mark.parametrize("upgrade", ["alembic", "startup"])
def test_sqlite_alembic_rolls_back_when_foreign_key_check_fails(
    tmp_path, monkeypatch, upgrade
):
    url = f"sqlite:///{tmp_path / 'invalid.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    previous = "a1b2c3d4e5e7"
    command.upgrade(config, previous)
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO family_member_preferences (family_member_id, preference_id) VALUES (99,99)"
                )
            )
        messages = []
        with pytest.raises(RuntimeError, match="foreign keys"):
            if upgrade == "alembic":
                command.upgrade(config, "head")
            else:
                run_lifespan(messages)
        if upgrade == "startup":
            assert [message["type"] for message in messages] == [
                "lifespan.startup.failed"
            ]
        with engine.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == previous
            )
            assert "user_id" not in {
                column["name"]
                for column in inspect(conn).get_columns("product_categories")
            }
    finally:
        engine.dispose()


def test_startup_schema_uses_supplied_in_memory_engine(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "invalid://must-not-be-used")
    engine = get_engine("sqlite:///:memory:")
    try:
        apply_schema(engine)
        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == (
                ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
            )
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize("migration_database", ["postgresql"], indirect=True)
@pytest.mark.parametrize("previous_revision", [None, "a1b2c3d4e5e7"])
def test_postgres_concurrent_startup(
    migration_database, previous_revision, monkeypatch
):
    engine, config = migration_database
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret")
    if previous_revision:
        command.upgrade(config, previous_revision)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (email,hashed_password,created_at) VALUES ('concurrent@test.example','hash','2026-01-01')"
                )
            )
            conn.execute(
                text("INSERT INTO product_categories (name) VALUES ('Legacy')")
            )

    # Separate processes exercise the database lock shared by distinct workers.
    startup = [
        sys.executable,
        "-c",
        "from tests.integration.test_personal_category_migration import run_lifespan; run_lifespan([])",
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            pool.submit(
                subprocess.run, startup, capture_output=True, text=True, timeout=30
            )
            for _ in range(2)
        ]
        for result in results:
            process = result.result()
            assert process.returncode == 0, process.stderr

    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one() == (ScriptDirectory.from_config(config).get_current_head())
        assert conn.execute(
            text("SELECT user_id,name FROM product_categories")
        ).all() == ([(1, "Legacy")] if previous_revision else [])
        assert conn.execute(text("SELECT COUNT(*) FROM units")).scalar_one() == 10

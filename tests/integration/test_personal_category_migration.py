import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.infrastructure.database.connection import apply_schema, get_engine


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


@pytest.mark.parametrize("upgrade", ["alembic", "startup"])
def test_empty_database(migration_database, upgrade):
    engine, config = migration_database
    if upgrade == "alembic":
        command.upgrade(config, "head")
    apply_schema(engine)
    for table in ("product_categories", "recipe_categories"):
        columns = {c["name"]: c for c in inspect(engine).get_columns(table)}
        assert columns["user_id"]["nullable"] is False
        with engine.connect() as conn:
            assert conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() == 0


@pytest.mark.parametrize("upgrade", ["alembic", "startup"])
def test_migrate_personal_category_catalog(migration_database, upgrade):
    engine, config = migration_database
    command.upgrade(config, "a1b2c3d4e5e7")
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
                "INSERT INTO preferences (id,user_id,name,type,mode) VALUES (:id,:id,'Preference','CATEGORY_BASED','BLOCKED')",
                "INSERT INTO preference_categories (preference_id,category_id) VALUES (:id,51)",
                "INSERT INTO preference_recipe_categories (preference_id,recipe_category_id) VALUES (:id,50)",
                "INSERT INTO recipe_ingredients (recipe_id,product_id,amount,unit) VALUES (:id,:id,10,'g')",
            ):
                conn.execute(text(stmt), {"id": owner})

    if upgrade == "alembic":
        command.upgrade(config, "head")
    apply_schema(engine)
    command.upgrade(config, "head")
    apply_schema(engine)
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
        for table in ("product_categories", "recipe_categories"):
            conn.execute(
                text(f"INSERT INTO {table} (user_id,name) VALUES (3,'After upgrade')")
            )
        if engine.dialect.name == "sqlite":
            assert conn.execute(text("PRAGMA foreign_key_check")).all() == []

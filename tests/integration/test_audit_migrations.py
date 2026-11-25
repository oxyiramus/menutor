"""Alembic upgrades must build a usable schema and preserve existing links."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.filterwarnings("error::sqlalchemy.exc.SAWarning")


def test_upgrade_empty_database(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'empty.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        tables = inspect(engine).get_table_names()
        assert {
            "users",
            "recipes",
            "menus",
            "menu_slots",
            "family_member_preferences",
        } <= set(tables)
        assert "member_ids" in {
            c["name"] for c in inspect(engine).get_columns("menu_slots")
        }
    finally:
        engine.dispose()


def test_upgrade_previous_revision_preserves_menu_links(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'previous.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "c2d3e4f5a6b7")
    engine = create_engine(url)
    try:
        with engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO users (id,email,nickname,hashed_password,created_at) VALUES (1,'migration@example.com','M','hash','2026-01-01')"
                )
            )
            c.execute(
                text(
                    "INSERT INTO recipe_categories (id,name,active) VALUES (900,'Migration',1)"
                )
            )
            c.execute(
                text(
                    "INSERT INTO recipes (id,user_id,name,category_id,servings,weight) VALUES (900,1,'Recipe',900,2,100)"
                )
            )
            c.execute(text("INSERT INTO menus (id,user_id,name) VALUES (900,1,'Keep')"))
            c.execute(
                text(
                    "INSERT INTO menu_slots (id,menu_id,day,meal_type,recipe_id,slot_position,member_ids) VALUES (900,900,0,'Завтрак',900,0,'[]')"
                )
            )
        command.upgrade(config, "head")
        with engine.connect() as c:
            assert (
                c.execute(text("SELECT name FROM menus WHERE id=900")).scalar()
                == "Keep"
            )
            assert c.execute(
                text(
                    "SELECT ms.menu_id,ms.recipe_id,mt.name FROM menu_slots ms JOIN meal_types mt ON mt.id=ms.meal_type_id WHERE ms.id=900"
                )
            ).one() == (900, 900, "Завтрак")
    finally:
        engine.dispose()

from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session

from backend.infrastructure.database.models import Base
from backend.infrastructure.database.personal_categories import (
    migrate_personal_categories,
)


def get_engine(db_url: str = "sqlite:///data/menutor.db") -> Engine:
    """Create a SQLAlchemy engine from a database URL.

    Accepts any SQLAlchemy-compatible URL:
      - sqlite:///data/menutor.db
      - sqlite:///:memory:
      - postgresql+psycopg2://user:pass@host:5432/dbname
    """
    if db_url.startswith("sqlite"):
        # Ensure parent directory exists for file-based SQLite
        if ":memory:" not in db_url:
            # Extract path from sqlite:///path
            db_path = db_url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        engine = create_engine(db_url)

        @event.listens_for(engine, "connect")
        def _enable_fk(conn, _record):  # type: ignore[no-untyped-def]
            conn.execute("PRAGMA foreign_keys = ON")

    else:
        engine = create_engine(db_url)

    return engine


def _is_sqlite(engine: Engine) -> bool:
    return engine.dialect.name == "sqlite"


# ── SQLite-only legacy migrations ────────────────────────────────────────


def _migrate_menu_slots(conn) -> None:  # type: ignore[no-untyped-def]
    """Migrate old menu_slots (no product_id) to new schema."""
    info = conn.execute(text("PRAGMA table_info(menu_slots)")).fetchall()
    columns = {row[1] for row in info}
    if "product_id" in columns:
        return
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS _menu_slots_backup (
            menu_id INTEGER, day INTEGER, meal_type TEXT,
            recipe_id INTEGER, servings_override REAL
        )
    """))
    conn.execute(
        text(
            "INSERT INTO _menu_slots_backup "
            "SELECT menu_id, day, meal_type, recipe_id, servings_override FROM menu_slots"
        )
    )
    conn.execute(text("DROP TABLE menu_slots"))
    conn.commit()


def _migrate_products_supplier(conn) -> None:  # type: ignore[no-untyped-def]
    info = conn.execute(text("PRAGMA table_info(products)")).fetchall()
    if "supplier" not in {row[1] for row in info}:
        conn.execute(
            text("ALTER TABLE products ADD COLUMN supplier TEXT NOT NULL DEFAULT ''")
        )
        conn.commit()


def _migrate_recipes_weight(conn) -> None:  # type: ignore[no-untyped-def]
    info = conn.execute(text("PRAGMA table_info(recipes)")).fetchall()
    if "weight" not in {row[1] for row in info}:
        conn.execute(
            text("ALTER TABLE recipes ADD COLUMN weight INTEGER NOT NULL DEFAULT 0")
        )
        conn.commit()


def _migrate_menu_slots_position(conn) -> None:  # type: ignore[no-untyped-def]
    info = conn.execute(text("PRAGMA table_info(menu_slots)")).fetchall()
    if "slot_position" not in {row[1] for row in info}:
        conn.execute(
            text(
                "ALTER TABLE menu_slots ADD COLUMN slot_position INTEGER NOT NULL DEFAULT 0"
            )
        )
        conn.commit()


def _run_sqlite_migrations(engine: Engine) -> bool:
    """Run SQLite-specific legacy migrations. Returns True if menu_slots backup exists."""
    had_menu_slots = False
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        had_menu_slots = "menu_slots" in tables
        if had_menu_slots:
            _migrate_menu_slots(conn)
        if "products" in tables:
            _migrate_products_supplier(conn)
        if "recipes" in tables:
            _migrate_recipes_weight(conn)
        if "menu_slots" in tables:
            _migrate_menu_slots_position(conn)
    return had_menu_slots


def _restore_sqlite_menu_slots_backup(engine: Engine) -> None:
    with engine.connect() as conn:
        backup_exists = conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='_menu_slots_backup'"
            )
        ).fetchone()
        if backup_exists:
            conn.execute(
                text(
                    "INSERT INTO menu_slots "
                    "(menu_id, day, meal_type, recipe_id, servings_override) "
                    "SELECT menu_id, day, meal_type, recipe_id, servings_override "
                    "FROM _menu_slots_backup"
                )
            )
            conn.execute(text("DROP TABLE _menu_slots_backup"))
            conn.commit()


# ── Public API ───────────────────────────────────────────────────────────


def apply_schema(engine: Engine) -> None:
    """Create all tables (idempotent). Runs legacy SQLite migrations first."""
    had_menu_slots = False
    if _is_sqlite(engine):
        had_menu_slots = _run_sqlite_migrations(engine)

    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        inspector = inspect(conn)
        if any(
            "user_id" not in {column["name"] for column in inspector.get_columns(table)}
            for table in ("product_categories", "recipe_categories")
        ):
            if _is_sqlite(engine):
                conn.exec_driver_sql("PRAGMA foreign_keys = OFF")
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                migrate_personal_categories(conn)
                if (
                    _is_sqlite(engine)
                    and conn.exec_driver_sql("PRAGMA foreign_key_check").first()
                ):
                    raise RuntimeError("Category migration left invalid foreign keys")
                conn.commit()
            finally:
                conn.rollback()
                if _is_sqlite(engine):
                    conn.exec_driver_sql("PRAGMA foreign_keys = ON")

    if had_menu_slots and _is_sqlite(engine):
        _restore_sqlite_menu_slots_backup(engine)


def seed_defaults(session: Session) -> None:
    """Populate the shared unit catalog."""
    session.execute(
        text(
            "INSERT INTO units (name, unit_group) VALUES (:n, :g) ON CONFLICT (name) DO NOTHING"
        ),
        [
            {"n": "g", "g": "weight"},
            {"n": "kg", "g": "weight"},
            {"n": "ml", "g": "volume"},
            {"n": "l", "g": "volume"},
            {"n": "tsp", "g": "volume"},
            {"n": "tbsp", "g": "volume"},
            {"n": "pcs", "g": "count_pcs"},
            {"n": "box", "g": "count_box"},
            {"n": "pack", "g": "count_pack"},
            {"n": "serv", "g": "servings"},
        ],
    )
    session.commit()

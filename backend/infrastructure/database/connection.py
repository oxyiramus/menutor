from pathlib import Path
from threading import Lock

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session

# Alembic's environment context is shared by threads in this process.
_alembic_lock = Lock()
_migrations_dir = Path(__file__).resolve().with_name("migrations")


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


def apply_schema(engine: Engine) -> None:
    """Upgrade the application's database to Alembic head before seeding."""
    config = Config()
    config.set_main_option("script_location", str(_migrations_dir))
    with _alembic_lock, engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


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

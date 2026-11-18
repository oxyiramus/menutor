"""Alembic environment configuration.

Reads DATABASE_URL from .config/.env (production) or falls back to
sqlite:///data/menutor.db (local development).
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Ensure project root is on sys.path so "backend" package is importable
_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import Connection, create_engine, inspect, pool

from backend.infrastructure.database.models import Base
from backend.infrastructure.database.personal_categories import (
    check_sqlite_foreign_keys,
    lock_postgres_schema,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    load_dotenv(_project_root / ".config" / ".env")
    return os.environ.get("DATABASE_URL", "sqlite:///data/menutor.db")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL script without connecting to the database.
    """
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection, *, startup: bool) -> None:
    sqlite = connection.dialect.name == "sqlite"
    restore_foreign_keys = False
    try:
        with connection.begin():
            lock_postgres_schema(connection)
            if sqlite:
                # Batch migrations rebuild tables referenced by foreign keys.
                restore_foreign_keys = bool(
                    connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
                )
                connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
                connection.exec_driver_sql("BEGIN IMMEDIATE")

            context.configure(connection=connection, target_metadata=target_metadata)
            migration = context.get_context()
            if startup and not migration.get_current_heads():
                tables = set(inspect(connection).get_table_names())
                if tables - {migration.version_table}:
                    raise RuntimeError(
                        "В базе данных есть таблицы, но отсутствует ревизия Alembic. "
                        "Проверьте схему и историю миграций перед запуском Menutor."
                    )

            with context.begin_transaction():
                context.run_migrations()
            check_sqlite_foreign_keys(connection)
    finally:
        if restore_foreign_keys:
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run_migrations(connection, startup=True)
        return

    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            _run_migrations(connection, startup=False)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

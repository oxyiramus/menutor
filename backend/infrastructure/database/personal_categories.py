"""Copy the former shared catalogs and remap their existing references."""

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import Connection


def lock_postgres_schema(conn: Connection) -> None:
    """Serialize startup and Alembic schema changes until the transaction ends."""
    if conn.dialect.name == "postgresql":
        conn.exec_driver_sql("SELECT pg_advisory_xact_lock(hashtext('menutor.schema'))")


def check_sqlite_foreign_keys(conn: Connection) -> None:
    if (
        conn.dialect.name == "sqlite"
        and conn.exec_driver_sql("PRAGMA foreign_key_check").first()
    ):
        raise RuntimeError("Database migration left invalid foreign keys")


def migrate_personal_categories(conn: Connection) -> None:
    operations = Operations(MigrationContext.configure(conn))
    for kind, preference_fk in (
        ("product", "category_id"),
        ("recipe", "recipe_category_id"),
    ):
        table = f"{kind}_categories"
        inspector = sa.inspect(conn)
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "user_id" in columns:
            continue

        unique_name = next(
            constraint["name"]
            for constraint in inspector.get_unique_constraints(table)
            if constraint["column_names"] == ["name"]
        )
        legacy_unique = unique_name or f"uq_{table}_name"
        with operations.batch_alter_table(
            table, naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}
        ) as batch:
            batch.drop_constraint(legacy_unique, type_="unique")
            batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
            if "color" not in columns:
                batch.add_column(sa.Column("color", sa.String(7), nullable=True))
            batch.create_unique_constraint(f"uq_{table}_user_name", ["user_id", "name"])
            batch.create_foreign_key(
                f"fk_{table}_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
            )

        conn.execute(
            sa.text(f"""
            INSERT INTO {table} (id, user_id, name, active, color)
            SELECT ids.max_id + ROW_NUMBER() OVER (ORDER BY u.id, c.id),
                   u.id, c.name, c.active, c.color
            FROM users u CROSS JOIN {table} c
            CROSS JOIN (SELECT COALESCE(MAX(id), 0) AS max_id FROM {table}) ids
            WHERE c.user_id IS NULL
        """)
        )
        preference_table = (
            "preference_categories"
            if kind == "product"
            else "preference_recipe_categories"
        )
        for child, fk, owner in (
            (f"{kind}s", "category_id", "child.user_id"),
            (
                preference_table,
                preference_fk,
                "(SELECT user_id FROM preferences WHERE id = child.preference_id)",
            ),
        ):
            conn.execute(
                sa.text(f"""
                UPDATE {child} AS child
                SET {fk} = (
                    SELECT personal.id FROM {table} legacy
                    JOIN {table} personal ON personal.name = legacy.name
                    WHERE legacy.id = child.{fk} AND personal.user_id = {owner}
                )
            """)
            )
        conn.execute(sa.text(f"DELETE FROM {table} WHERE user_id IS NULL"))
        with operations.batch_alter_table(table) as batch:
            batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

        if conn.dialect.name == "postgresql":
            # Upgrade also handles catalogs populated with explicitly assigned IDs.
            conn.execute(
                sa.text(f"""
                SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                              COALESCE(MAX(id), 1), COUNT(*) > 0)
                FROM {table}
            """)
            )

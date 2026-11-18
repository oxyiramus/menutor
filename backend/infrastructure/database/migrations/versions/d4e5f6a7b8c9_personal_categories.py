"""Give each user independent copies of the category catalogs."""

from alembic import op

from backend.infrastructure.database.personal_categories import (
    migrate_personal_categories,
)

revision = "d4e5f6a7b8c9"
down_revision = "a1b2c3d4e5e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrate_personal_categories(op.get_bind())


def downgrade() -> None:
    raise NotImplementedError(
        "Personal category catalogs cannot be merged without data loss"
    )

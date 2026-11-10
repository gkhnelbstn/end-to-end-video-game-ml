"""Add background_image and clip to games.

These columns were added to the Game model without a migration, so a database
built with Alembic was missing them.

Revision ID: 8f3a1c2b7e90
Revises: d24eb6d10ce4
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8f3a1c2b7e90"
down_revision: str | None = "d24eb6d10ce4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # IF NOT EXISTS: databases first created by `create_all` may already have them.
    op.execute("ALTER TABLE games ADD COLUMN IF NOT EXISTS background_image VARCHAR")
    op.execute("ALTER TABLE games ADD COLUMN IF NOT EXISTS clip VARCHAR")


def downgrade() -> None:
    op.drop_column("games", "clip")
    op.drop_column("games", "background_image")

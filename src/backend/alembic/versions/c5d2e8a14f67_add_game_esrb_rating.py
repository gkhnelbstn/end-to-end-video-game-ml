"""Add the ESRB age rating to games.

Revision ID: c5d2e8a14f67
Revises: b71e4d09c3a2
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c5d2e8a14f67"
down_revision: str | None = "b71e4d09c3a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE games ADD COLUMN IF NOT EXISTS esrb_rating VARCHAR")


def downgrade() -> None:
    op.drop_column("games", "esrb_rating")

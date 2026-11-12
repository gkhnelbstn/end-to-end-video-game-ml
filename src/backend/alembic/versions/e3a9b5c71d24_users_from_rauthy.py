"""Dashboard accounts move to Rauthy: users get a `sub`, lose their password.

Revision ID: e3a9b5c71d24
Revises: c5d2e8a14f67
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3a9b5c71d24"
down_revision: str | None = "c5d2e8a14f67"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("sub", sa.String(), nullable=True))
    op.create_index(op.f("ix_users_sub"), "users", ["sub"], unique=True)
    op.alter_column("users", "email", existing_type=sa.String(), nullable=True)
    op.drop_column("users", "hashed_password")


def downgrade() -> None:
    # Old accounts get an unusable password; there is nothing to restore.
    op.add_column(
        "users",
        sa.Column("hashed_password", sa.String(), nullable=False, server_default="!"),
    )
    op.alter_column("users", "hashed_password", server_default=None)
    op.execute("DELETE FROM users WHERE email IS NULL")
    op.alter_column("users", "email", existing_type=sa.String(), nullable=False)
    op.drop_index(op.f("ix_users_sub"), table_name="users")
    op.drop_column("users", "sub")

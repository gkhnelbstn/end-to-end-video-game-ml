"""Support games from sources other than RAWG (Steam, IGDB).

- games.steam_appid, games.igdb_id: the game's id in those catalogues
- games.critic_rating: IGDB's aggregated critic rating (kept apart from Metacritic)
- id sequences start at GENERATED_ID_FLOOR, so generated ids never collide with RAWG ids

Revision ID: b71e4d09c3a2
Revises: 8f3a1c2b7e90
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b71e4d09c3a2"
down_revision: str | None = "8f3a1c2b7e90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GENERATED_ID_FLOOR = 100_000_000
TABLES_WITH_GENERATED_IDS = ("games", "genres", "platforms", "stores", "tags")


def upgrade() -> None:
    op.add_column("games", sa.Column("critic_rating", sa.Float(), nullable=True))
    op.add_column("games", sa.Column("steam_appid", sa.Integer(), nullable=True))
    op.add_column("games", sa.Column("igdb_id", sa.Integer(), nullable=True))
    op.create_index("ix_games_steam_appid", "games", ["steam_appid"], unique=True)
    op.create_index("ix_games_igdb_id", "games", ["igdb_id"], unique=True)

    for table in TABLES_WITH_GENERATED_IDS:
        op.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
            f"GREATEST((SELECT COALESCE(MAX(id), 0) FROM {table}), {GENERATED_ID_FLOOR}))"
        )


def downgrade() -> None:
    op.drop_index("ix_games_igdb_id", table_name="games")
    op.drop_index("ix_games_steam_appid", table_name="games")
    op.drop_column("games", "igdb_id")
    op.drop_column("games", "steam_appid")
    op.drop_column("games", "critic_rating")

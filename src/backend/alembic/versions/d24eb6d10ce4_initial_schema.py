"""
Revision ID: d24eb6d10ce4
Revises: 
Create Date: 2025-08-08 21:33:07.431266

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd24eb6d10ce4'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enums
    userrole = postgresql.ENUM('user', 'admin', name='userrole')
    userrole.create(op.get_bind(), checkfirst=True)
    # Use a non-creating enum for column definitions to avoid duplicate type creation
    userrole_nocreate = postgresql.ENUM('user', 'admin', name='userrole', create_type=False)

    # Core tables
    op.create_table(
        'games',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('released', sa.DateTime(), nullable=True),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('ratings_count', sa.Integer(), nullable=True),
        sa.Column('metacritic', sa.Integer(), nullable=True),
        sa.Column('playtime', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_games_slug', 'games', ['slug'], unique=True)
    op.create_index('ix_games_name', 'games', ['name'], unique=False)

    op.create_table(
        'genres',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
    )
    op.create_index('ix_genres_name', 'genres', ['name'], unique=True)
    op.create_index('ix_genres_slug', 'genres', ['slug'], unique=True)

    op.create_table(
        'platforms',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
    )
    op.create_index('ix_platforms_name', 'platforms', ['name'], unique=True)
    op.create_index('ix_platforms_slug', 'platforms', ['slug'], unique=True)

    op.create_table(
        'stores',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
    )
    op.create_index('ix_stores_name', 'stores', ['name'], unique=True)
    op.create_index('ix_stores_slug', 'stores', ['slug'], unique=True)

    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
    )
    op.create_index('ix_tags_name', 'tags', ['name'], unique=True)
    op.create_index('ix_tags_slug', 'tags', ['slug'], unique=True)

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('role', userrole_nocreate, server_default='user', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'admin_users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_admin_users_username', 'admin_users', ['username'], unique=True)

    # Association tables
    op.create_table(
        'game_genres',
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('genre_id', sa.Integer(), sa.ForeignKey('genres.id', ondelete='CASCADE'), primary_key=True),
    )
    op.create_table(
        'game_platforms',
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('platform_id', sa.Integer(), sa.ForeignKey('platforms.id', ondelete='CASCADE'), primary_key=True),
    )
    op.create_table(
        'game_stores',
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('store_id', sa.Integer(), sa.ForeignKey('stores.id', ondelete='CASCADE'), primary_key=True),
    )
    op.create_table(
        'game_tags',
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
    )
    op.create_table(
        'user_favorite_games',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id', ondelete='CASCADE'), primary_key=True),
    )


def downgrade() -> None:
    # Drop association tables first (FK dependencies)
    op.drop_table('user_favorite_games')
    op.drop_table('game_tags')
    op.drop_table('game_stores')
    op.drop_table('game_platforms')
    op.drop_table('game_genres')

    # Drop core tables
    op.drop_index('ix_admin_users_username', table_name='admin_users')
    op.drop_table('admin_users')

    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

    op.drop_index('ix_tags_slug', table_name='tags')
    op.drop_index('ix_tags_name', table_name='tags')
    op.drop_table('tags')

    op.drop_index('ix_stores_slug', table_name='stores')
    op.drop_index('ix_stores_name', table_name='stores')
    op.drop_table('stores')

    op.drop_index('ix_platforms_slug', table_name='platforms')
    op.drop_index('ix_platforms_name', table_name='platforms')
    op.drop_table('platforms')

    op.drop_index('ix_genres_slug', table_name='genres')
    op.drop_index('ix_genres_name', table_name='genres')
    op.drop_table('genres')

    op.drop_index('ix_games_name', table_name='games')
    op.drop_index('ix_games_slug', table_name='games')
    op.drop_table('games')

    # Drop enum
    userrole = postgresql.ENUM('user', 'admin', name='userrole')
    userrole.drop(op.get_bind(), checkfirst=True)

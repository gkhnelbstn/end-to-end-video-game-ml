"""Alembic migrations must produce exactly the schema the models describe.

Needs a PostgreSQL database: set TEST_DATABASE_URL (CI does). Skipped otherwise.
The database is wiped, so never point this at one you care about.
"""

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set")


def alembic(*args: str) -> subprocess.CompletedProcess:
    # A subprocess, because the app (and so Alembic's env.py) binds DATABASE_URL at import.
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "src/backend/alembic.ini", *args],
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL, "PYTHONPATH": os.getcwd()},
        capture_output=True,
        text=True,
    )


def test_migrations_match_models():
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    upgrade = alembic("upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr

    # `alembic check` fails if autogenerate would still produce a migration.
    check = alembic("check")
    assert check.returncode == 0, check.stdout + check.stderr

    with engine.begin() as conn:
        # The enum stores the lowercase values the User model sends.
        conn.execute(text("INSERT INTO users (sub, email) VALUES ('account', 'a@b.c')"))
        assert conn.execute(text("SELECT role::text, is_active FROM users")).one() == (
            "user",
            True,
        )

    downgrade = alembic("downgrade", "base")
    assert downgrade.returncode == 0, downgrade.stderr
    engine.dispose()

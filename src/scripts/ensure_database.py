"""Create a PostgreSQL database if it does not exist yet.

    python -m src.scripts.ensure_database postgresql+psycopg://user:pass@host:5432/name

Used by the MLflow service to get its own database on the shared Postgres server.
Connects to the server's `postgres` maintenance database to run CREATE DATABASE.
"""

import sys
import time

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


def ensure_database(url: str, attempts: int = 30) -> bool:
    """Returns True if the database was created, False if it already existed."""
    parsed = make_url(url)
    conninfo = {
        "host": parsed.host,
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
        "dbname": "postgres",
    }
    for attempt in range(attempts):
        try:
            with psycopg.connect(**conninfo, autocommit=True) as conn:
                exists = conn.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (parsed.database,)
                ).fetchone()
                if exists:
                    return False
                conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(parsed.database)))
                return True
        except psycopg.OperationalError:
            if attempt == attempts - 1:
                raise
            time.sleep(2)
    return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    created = ensure_database(sys.argv[1])
    print(f"Database {make_url(sys.argv[1]).database!r} {'created' if created else 'exists'}")

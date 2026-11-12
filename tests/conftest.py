"""Shared fixtures.

The API tests run against a throwaway SQLite database, so they need no services.
`test_migrations.py` additionally checks the Alembic migrations against PostgreSQL
when TEST_DATABASE_URL is set (as it is in CI).
"""

import os
import tempfile
import time
from datetime import datetime

# The app builds its engine at import time, so point it at SQLite before importing it.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.backend import database, models
from src.backend.auth import TokenVerifier, get_verifier


@pytest.fixture
def db() -> Session:
    """A session on a freshly created database with a small catalogue."""
    models.Base.metadata.create_all(database.engine)

    with database.SessionLocal() as session:
        action = models.Genre(id=1, name="Action", slug="action")
        rpg = models.Genre(id=2, name="RPG", slug="rpg")
        pc = models.Platform(id=1, name="PC", slug="pc")
        ps5 = models.Platform(id=2, name="PlayStation 5", slug="playstation-5")
        session.add_all(
            [
                models.Game(
                    id=1,
                    name="Game A",
                    slug="game-a",
                    rating=4.5,
                    released=datetime(2023, 1, 1),
                    genres=[action],
                    platforms=[pc],
                ),
                models.Game(
                    id=2,
                    name="Game B",
                    slug="game-b",
                    rating=3.5,
                    released=datetime(2022, 1, 1),
                    genres=[rpg],
                    platforms=[ps5],
                ),
                models.Game(
                    id=3,
                    name="Game C",
                    slug="game-c",
                    rating=4.8,
                    released=datetime(2023, 5, 1),
                    genres=[action],
                    platforms=[ps5],
                ),
                models.User(id=1, sub="account-1", email="test@example.com"),
            ]
        )
        session.commit()
        yield session

    models.Base.metadata.drop_all(database.engine)


# Access tokens in tests are signed with a throwaway key instead of Rauthy's.
ISSUER = "http://localhost:8080/auth/v1/"
AUDIENCE = "game-insight"
_SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class LocalVerifier(TokenVerifier):
    def __init__(self):
        self.issuer = ISSUER
        self.audience = AUDIENCE

    def signing_key(self, token: str):
        return _SIGNING_KEY.public_key()


def make_token(sub: str = "account-1", expires_in: int = 300, key=None, **claims) -> str:
    """An access token shaped like Rauthy's; `claims` override or add fields."""
    now = int(time.time())
    payload = {"iss": ISSUER, "aud": AUDIENCE, "sub": sub, "iat": now, "exp": now + expires_in}
    payload.update(claims)
    return jwt.encode(payload, key or _SIGNING_KEY, algorithm="RS256")


def bearer(sub: str = "account-1", **claims) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub, **claims)}"}


@pytest.fixture
def client(db) -> TestClient:
    from src.backend.main import app

    app.dependency_overrides[get_verifier] = LocalVerifier
    # Not used as a context manager: the lifespan (scheduler, admin bootstrap) stays off.
    yield TestClient(app)
    app.dependency_overrides.clear()

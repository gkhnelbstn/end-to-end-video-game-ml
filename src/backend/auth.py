"""Dashboard sign-in: checks access tokens issued by Rauthy (OpenID Connect).

The dashboard signs people in with Rauthy (authorization code + PKCE) and sends the
access token as `Authorization: Bearer ...`. Here the token's signature is checked
against Rauthy's published keys, along with its issuer, audience and expiry.
"""

from functools import lru_cache
from typing import Any

import jwt

from . import config


class InvalidToken(Exception):
    """The token is missing, malformed, expired, or not issued for this app."""


class TokenVerifier:
    def __init__(self, issuer: str, audience: str, jwks_url: str):
        self.issuer = issuer
        self.audience = audience
        # Caches the signing keys and refetches when a token names an unknown key id.
        self._keys = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600, timeout=5)

    def signing_key(self, token: str) -> Any:
        try:
            return self._keys.get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError:
            raise
        except jwt.PyJWTError as exc:
            raise InvalidToken(str(exc)) from exc

    def verify(self, token: str) -> dict[str, Any]:
        key = self.signing_key(token)
        try:
            return jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
                leeway=30,
            )
        except jwt.PyJWTError as exc:
            raise InvalidToken(str(exc)) from exc


@lru_cache
def get_verifier() -> TokenVerifier:
    return TokenVerifier(config.OIDC_ISSUER, config.OIDC_AUDIENCE, config.OIDC_JWKS_URL)

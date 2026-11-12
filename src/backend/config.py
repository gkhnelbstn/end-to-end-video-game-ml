"""Runtime configuration, read from environment variables."""

import os

DATABASE_URL = os.environ.get("DATABASE_URL")
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

# Signs the admin panel session cookie. The default is for local development only.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")

# Dashboard sign-in with Rauthy (OpenID Connect). The issuer is the public URL the
# browser sees, which must match the tokens' `iss` exactly; the keys are fetched over
# the internal network. The audience is the dashboard's client id in Rauthy.
OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "http://localhost:8080/auth/v1/")
OIDC_JWKS_URL = os.environ.get("OIDC_JWKS_URL", "http://rauthy:8080/auth/v1/oidc/certs")
OIDC_AUDIENCE = os.environ.get("OIDC_AUDIENCE", "game-insight")

# Credentials of the admin user created on first startup (local development defaults).
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "adminpass")

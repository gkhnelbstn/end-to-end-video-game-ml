"""
Configuration for the FastAPI Admin panel.
"""
import os
from fastapi_admin.app import app as admin_app
from fastapi_admin.resources import Model
from fastapi_admin.providers.login import UsernamePasswordProvider
from passlib.context import CryptContext
from .models import User, Game, Genre, Platform, Store, Tag, UserRole
from .database import SessionLocal

# In a real application, you would have a more secure way of managing the secret
# key, e.g., by loading it from an environment variable.
ADMIN_SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", "your-super-secret-key")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Authentication provider
class AdminAuthProvider(UsernamePasswordProvider):
    async def login(self, username: str, password: str) -> User:
        db = SessionLocal()
        user = db.query(User).filter(User.email == username).first()
        db.close()

        if not user:
            return None
        if not pwd_context.verify(password, user.hashed_password):
            return None
        if user.role != UserRole.ADMIN:
            return None
        return user

    async def get_user(self, username: str) -> User:
        db = SessionLocal()
        user = db.query(User).filter(User.email == username).first()
        db.close()
        return user

# Initialize the admin app with the auth provider
admin_app.configure(
    secret_key=ADMIN_SECRET_KEY,
    auth_provider=AdminAuthProvider(),
)

@admin_app.register
class UserAdmin(Model):
    """Admin resource for the User model."""
    model = User
    icon = "fas fa-user"
    fields = ["id", "email", "is_active", "role", "created_at"]

@admin_app.register
class GameAdmin(Model):
    """Admin resource for the Game model."""
    model = Game
    icon = "fas fa-gamepad"
    fields = ["id", "name", "slug", "released", "rating", "metacritic"]

@admin_app.register
class GenreAdmin(Model):
    """Admin resource for the Genre model."""
    model = Genre
    icon = "fas fa-tag"
    fields = ["id", "name", "slug"]

@admin_app.register
class PlatformAdmin(Model):
    """Admin resource for the Platform model."""
    model = Platform
    icon = "fas fa-laptop"
    fields = ["id", "name", "slug"]

@admin_app.register
class StoreAdmin(Model):
    """Admin resource for the Store model."""
    model = Store
    icon = "fas fa-store"
    fields = ["id", "name", "slug"]

@admin_app.register
class TagAdmin(Model):
    """Admin resource for the Tag model."""
    model = Tag
    icon = "fas fa-hashtag"
    fields = ["id", "name", "slug"]

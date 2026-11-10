"""SQLAdmin panel: session-based login and model views."""

from pathlib import Path

from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from starlette.requests import Request

from . import config, security
from .database import SessionLocal, engine
from .models import AdminUser, Game, Genre, Platform, Store, Tag, User

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form.get("username"), form.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return False

        with SessionLocal() as db:
            admin_user = db.scalar(
                select(AdminUser).where(AdminUser.username == username, AdminUser.is_active)
            )
            if admin_user and security.verify_password(password, admin_user.hashed_password):
                request.session.update({"admin_user": admin_user.username})
                return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("admin_user") is not None


def create_admin(app) -> Admin:
    return Admin(
        app=app,
        engine=engine,
        authentication_backend=AdminAuth(secret_key=config.SECRET_KEY),
        templates_dir=str(TEMPLATES_DIR),
    )


class GameAdmin(ModelView, model=Game):
    name = "Game"
    name_plural = "Games"
    icon = "fa-solid fa-gamepad"

    column_list = [Game.id, Game.name, Game.rating, Game.released, Game.metacritic]
    column_searchable_list = [Game.name]
    column_sortable_list = [Game.name, Game.rating, Game.released]
    form_excluded_columns = [Game.favorited_by]
    # Look-up tables are large (tens of thousands of tags): load options on demand.
    form_ajax_refs = {
        "genres": {"fields": ("name",)},
        "platforms": {"fields": ("name",)},
        "stores": {"fields": ("name",)},
        "tags": {"fields": ("name",)},
    }

    page_size = 50
    page_size_options = [25, 50, 100, 200]


class _LookupAdmin(ModelView):
    column_list = ["id", "name", "slug"]
    column_searchable_list = ["name"]
    form_excluded_columns = ["games"]


class GenreAdmin(_LookupAdmin, model=Genre):
    name = "Genre"
    name_plural = "Genres"
    icon = "fa-solid fa-tags"


class PlatformAdmin(_LookupAdmin, model=Platform):
    name = "Platform"
    name_plural = "Platforms"
    icon = "fa-solid fa-desktop"


class StoreAdmin(_LookupAdmin, model=Store):
    name = "Store"
    name_plural = "Stores"
    icon = "fa-solid fa-store"


class TagAdmin(_LookupAdmin, model=Tag):
    name = "Tag"
    name_plural = "Tags"
    icon = "fa-solid fa-hashtag"


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-users"

    column_list = [User.id, User.email, User.is_active, User.role, User.created_at]
    column_searchable_list = [User.email]
    form_excluded_columns = [User.hashed_password, User.favorite_games]
    # Users register through the API, which hashes their password.
    can_create = False


class AdminUserAdmin(ModelView, model=AdminUser):
    name = "Admin User"
    name_plural = "Admin Users"
    icon = "fa-solid fa-user-shield"

    column_list = [AdminUser.id, AdminUser.username, AdminUser.is_active, AdminUser.created_at]
    column_searchable_list = [AdminUser.username]
    form_excluded_columns = [AdminUser.hashed_password]
    # Created with `python -m src.backend.create_admin`, which hashes the password.
    can_create = False


def setup_admin_views(admin: Admin) -> Admin:
    for view in (
        GameAdmin,
        GenreAdmin,
        PlatformAdmin,
        StoreAdmin,
        TagAdmin,
        UserAdmin,
        AdminUserAdmin,
    ):
        admin.add_view(view)
    return admin

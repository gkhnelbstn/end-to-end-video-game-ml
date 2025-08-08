# src/backend/admin.py

from sqladmin import Admin, ModelView, BaseView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .database import engine, SessionLocal
from .models import Game, Platform, Genre, Store, Tag, AdminUser, User
from .celery_app import celery_app
# from .celery_admin import CeleryMonitoringView  # Removed due to routing issues


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        
        # Check if required fields exist
        if "username" not in form or "password" not in form:
            print("Login error: Missing required fields")
            return False
            
        username, password = form["username"], form["password"]

        db: Session = SessionLocal()
        try:
            admin_user = db.query(AdminUser).filter(
                AdminUser.username == username,
                AdminUser.is_active == True
            ).first()

            if admin_user and pwd_context.verify(password, admin_user.hashed_password):
                # JWT token oluşturabilir veya session kullanabilirsiniz
                request.session.update({"admin_user": admin_user.username})
                print("Login successful")
                return True
        except Exception as e:
            print(f"Login error: {e}")
        finally:
            db.close()

        print("Login failed")
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        print("Logout successful")
        return True

    async def authenticate(self, request: Request) -> bool:
        # Oturum açmış kullanıcı var mı kontrol et
        admin_user = request.session.get("admin_user", None)
        if admin_user is not None:
            print("Authenticated user found")
            return True
        else:
            print("No authenticated user found")
            return False


# Authentication backend'i oluştur
authentication_backend = AdminAuth(secret_key="your-secret-key-change-this-in-production")


# Admin interface'i oluşturacak fonksiyon
def create_admin(app):
    """Admin panelini oluştur"""
    admin = Admin(
        app=app,
        engine=engine,
        authentication_backend=authentication_backend,
        templates_dir="/app/src/backend/templates"  # Custom templates directory (absolute path for Docker)
    )
    return admin


# Model View'leri tanımla
class GameAdmin(ModelView, model=Game):
    name = "Games"
    icon = "fa-solid fa-gamepad"

    column_list = [
        Game.id,
        Game.name,
        Game.rating,
        Game.released,
        Game.metacritic
    ]
    column_searchable_list = [Game.name]
    column_sortable_list = [Game.name, Game.rating, Game.released]
    # SQLAdmin >=0.21.0 filter API expects filter objects; temporarily disable to avoid errors
    column_filters = []

    # Sayfa başına gösterilecek kayıt sayısı
    page_size = 50
    page_size_options = [25, 50, 100, 200]


class GenreAdmin(ModelView, model=Genre):
    name = "Genres"
    icon = "fa-solid fa-tags"

    column_list = [Genre.id, Genre.name, Genre.slug]
    column_searchable_list = [Genre.name]


class PlatformAdmin(ModelView, model=Platform):
    name = "Platforms"
    icon = "fa-solid fa-desktop"

    column_list = [Platform.id, Platform.name, Platform.slug]
    column_searchable_list = [Platform.name]


class StoreAdmin(ModelView, model=Store):
    name = "Stores"
    icon = "fa-solid fa-store"

    column_list = [Store.id, Store.name, Store.slug]
    column_searchable_list = [Store.name]


class TagAdmin(ModelView, model=Tag):
    name = "Tags"
    icon = "fa-solid fa-hashtag"

    column_list = [Tag.id, Tag.name, Tag.slug]
    column_searchable_list = [Tag.name]


class UserAdmin(ModelView, model=User):
    name = "Users"
    icon = "fa-solid fa-users"

    column_list = [User.id, User.email, User.is_active, User.role, User.created_at]
    column_searchable_list = [User.email]
    # Disable problematic column_filters; can be replaced with proper filter objects later
    column_filters = []

    # Şifre alanını gizle
    # column_exclude_list = [User.hashed_password]
    form_excluded_columns = [User.hashed_password, User.favorite_games]


class AdminUserAdmin(ModelView, model=AdminUser):
    name = "Admin Users"
    icon = "fa-solid fa-user-shield"

    column_list = [AdminUser.id, AdminUser.username, AdminUser.is_active, AdminUser.created_at]
    column_searchable_list = [AdminUser.username]
    column_filters = []

    # Şifre alanını gizle
    # column_exclude_list = [AdminUser.hashed_password]
    form_excluded_columns = [AdminUser.hashed_password]


# View'leri admin'e ekleyecek fonksiyon
def setup_admin_views(admin):
    """Admin view'lerini ekle"""
    admin.add_view(GameAdmin)
    admin.add_view(GenreAdmin)
    admin.add_view(PlatformAdmin)
    admin.add_view(StoreAdmin)
    admin.add_view(TagAdmin)
    admin.add_view(UserAdmin)
    admin.add_view(AdminUserAdmin)
    return admin
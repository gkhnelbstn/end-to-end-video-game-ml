# src/backend/admin.py
from fastapi_admin.app import app as admin_app
from fastapi_admin.resources import Model
from .models import AdminUser, Game, Platform

@admin_app.register
class AdminUserAdmin(Model):
    resource = AdminUser
    fields = [
        "id",
        "username",
        "is_active",
        "created_at",
    ]

@admin_app.register
class GameAdmin(Model):
    resource = Game
    fields = [
        "id",
        "name",
        "slug",
        "released",
        "rating",
        "background_image",
    ]

@admin_app.register
class PlatformAdmin(Model):
    resource = Platform
    fields = [
        "id",
        "name",
        "slug",
    ]
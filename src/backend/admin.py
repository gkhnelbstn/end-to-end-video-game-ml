# src/backend/admin.py

from sqladmin import Admin, ModelView
from fastapi import FastAPI # ✅ FastAPI'yi import edin
from .database import engine
from .models import Game, Platform, AdminUser

# ✅ Geçici bir FastAPI örneği oluşturun
# Bu, sqladmin'in doğru çalışmasını sağlar
_temp_app = FastAPI()

# Admin nesnesini oluşturun, app parametresini geçici app ile geçirin
admin = Admin(app=_temp_app, engine=engine)

# Model view'leri tanımlayın
class GameAdmin(ModelView, model=Game):
    column_list = [Game.id, Game.name]

class PlatformAdmin(ModelView, model=Platform):
    column_list = [Platform.id, Platform.name]

class AdminUserAdmin(ModelView, model=AdminUser):
    column_list = [AdminUser.id, AdminUser.username]

# Admin view'lerini ekleyin
admin.add_view(GameAdmin)
admin.add_view(PlatformAdmin)
admin.add_view(AdminUserAdmin)

# main.py dosyasında şu satırı kullandığınızdan emin olun:
# app.mount("/admin", admin.app)
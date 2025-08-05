# src/backend/admin.py

from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from .database import engine, SessionLocal
from .models import Game, Platform, Genre, Store, Tag, AdminUser, User
from src.backend.celery_app import celery_app
from redbeat import RedBeatSchedulerEntry
import json
from datetime import datetime

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form["username"], form["password"]

        db: Session = SessionLocal()
        try:
            admin_user = db.query(AdminUser).filter(
                AdminUser.username == username,
                AdminUser.is_active == True
            ).first()

            if admin_user and pwd_context.verify(password, admin_user.hashed_password):
                request.session.update({"admin_user": admin_user.username})
                return True
        finally:
            db.close()

        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("admin_user") is not None


authentication_backend = AdminAuth(secret_key="your-secret-key-change-this")


def create_admin(app):
    """Admin interface'i oluştur ve app'e bağla"""
    admin = Admin(
        app=app,
        engine=engine,
        authentication_backend=authentication_backend,
        title="Game Insight Admin"
    )
    return admin


# Model View'leri
class GameAdmin(ModelView, model=Game):
    name = "Games"
    icon = "fa-solid fa-gamepad"
    column_list = [Game.id, Game.name, Game.rating, Game.released, Game.metacritic]
    column_searchable_list = [Game.name]
    column_sortable_list = [Game.name, Game.rating, Game.released]
    page_size = 50


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
    form_excluded_columns = [User.hashed_password, User.favorite_games]


class AdminUserAdmin(ModelView, model=AdminUser):
    name = "Admin Users"
    icon = "fa-solid fa-user-shield"
    column_list = [AdminUser.id, AdminUser.username, AdminUser.is_active, AdminUser.created_at]
    form_excluded_columns = [AdminUser.hashed_password]


def setup_admin_views(admin):
    """Admin view'leri ekle"""
    admin.add_view(GameAdmin)
    admin.add_view(GenreAdmin)
    admin.add_view(PlatformAdmin)
    admin.add_view(StoreAdmin)
    admin.add_view(TagAdmin)
    admin.add_view(UserAdmin)
    admin.add_view(AdminUserAdmin)

    # ✅ Task yönetimi view'ını ekle
    _add_task_management_view(admin)


# 🔥 YENİ: Task Yönetim Sayfası
def _add_task_management_view(admin):
    app = admin.app

    TASK_DEFINITIONS = {
        "fetch_games_for_month_task": {
            "name": "Aylık Oyun Verisi Çek",
            "description": "Belirli bir ay için oyun verisi çeker",
            "params": ["year", "month"],
        },
        "fetch_monthly_updates_task": {
            "name": "Aylık Güncellemeler",
            "description": "Geçen ayın verisini çeker",
            "params": [],
        },
        "fetch_weekly_updates_task": {
            "name": "Haftalık Güncellemeler",
            "description": "Son 7 günün güncellenen oyunlarını çeker",
            "params": [],
        },
    }

    @app.get("/admin/tasks", response_class=HTMLResponse)
    async def task_page(request: Request):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Celery Task Yönetimi</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .card {{ border: 1px solid #ddd; padding: 15px; margin: 15px 0; border-radius: 8px; background: #f9f9f9; }}
                input, select, button {{ padding: 8px; margin: 5px 0; width: 100%; }}
                button {{ background: #007bff; color: white; border: none; cursor: pointer; }}
                button:hover {{ background: #0056b3; }}
                .param-fields {{ margin-top: 10px; padding: 10px; background: #f0f0f0; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <h1>🎯 Celery Task Yönetimi</h1>

            <div class="card">
                <h2>🔧 Manuel Tetikleme</h2>
                <select id="taskSelect" onchange="toggleParams()">{"".join(f'<option value="{k}">{v["name"]} - {v["description"]}</option>' for k,v in TASK_DEFINITIONS.items())}</select>
                <div id="paramFields" class="param-fields"></div>
                <button onclick="triggerTask()">Tetikle</button>
            </div>

            <div class="card">
                <h2>⏰ Zamanlama Ekle</h2>
                <select id="scheduleTaskSelect" onchange="toggleScheduleParams()">{"".join(f'<option value="{k}">{v["name"]}</option>' for k,v in TASK_DEFINITIONS.items())}</select>
                <div id="scheduleParamFields" class="param-fields"></div>
                <input type="number" id="interval" placeholder="Aralık (saniye)" value="86400">
                <input type="text" id="scheduleName" placeholder="Zamanlama İsmi" value="scheduled_{int(datetime.now().timestamp())}">
                <button onclick="scheduleTask()">Zamanla</button>
            </div>

            <div class="card">
                <h2>📋 Aktif Zamanlamalar</h2>
                <div id="schedulesList">Yükleniyor...</div>
            </div>

            <script>
            function toggleParams() {{
                const task = document.getElementById('taskSelect').value;
                const container = document.getElementById('paramFields');
                container.innerHTML = '';
                const params = {json.dumps({k: v["params"] for k,v in TASK_DEFINITIONS.items()})}[task];
                if (params.length > 0) {{
                    params.forEach(p => container.innerHTML += `<div><label>${{p}}:</label><input id="param_${{p}}" type="text"></div>`);
                }}
            }}

            function triggerTask() {{
                const task = document.getElementById('taskSelect').value;
                const params = {{}};
                const paramNames = {json.dumps({k: v["params"] for k,v in TASK_DEFINITIONS.items()})}[task];
                paramNames.forEach(p => params[p] = document.getElementById('param_' + p).value);
                fetch('/admin/api/trigger-task', {{method: 'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{task, params}})}})
                .then(r => r.json()).then(d => alert('Tetiklendi! Task ID: ' + d.task_id));
            }}

            function scheduleTask() {{
                const task = document.getElementById('scheduleTaskSelect').value;
                const interval = parseInt(document.getElementById('interval').value);
                const name = document.getElementById('scheduleName').value;
                const params = {{}};
                const paramNames = {json.dumps({k: v["params"] for k,v in TASK_DEFINITIONS.items()})}[task];
                paramNames.forEach(p => {{
                    const el = document.getElementById('schedule_param_' + p);
                    if (el) params[p] = el.value;
                }});
                fetch('/admin/api/schedule-task', {{method: 'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{task, interval, name, params}})}})
                .then(r => r.json()).then(d => {{
                    alert('Zamanlama eklendi!');
                    loadSchedules();
                }});
            }}

            function loadSchedules() {{
                fetch('/admin/api/scheduled-tasks').then(r => r.json()).then(schedules => {{
                    const container = document.getElementById('schedulesList');
                    container.innerHTML = schedules.length ? '' : '<p>Hiç zamanlama yok.</p>';
                    schedules.forEach(s => {{
                        container.innerHTML += `
                            <div style="border-bottom:1px solid #eee; padding:10px">
                                <b>${{s.name}}</b> → ${{s.task}} (Her ${{s.interval}} sn)
                                <button onclick="deleteSchedule('$${s.name}')" style="background:#dc3545; color:white; padding:5px 10px;">Sil</button>
                            </div>`;
                    }});
                }});
            }}

            function deleteSchedule(name) {{
                if (confirm(name + ' isimli zamanlama silinsin mi?')) {{
                    fetch('/admin/api/delete-schedule/' + name, {{method: 'DELETE'}})
                        .then(() => loadSchedules());
                }}
            }}

            document.addEventListener('DOMContentLoaded', () => {{
                toggleParams();
                loadSchedules();
            }});
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html)

    @app.post("/admin/api/trigger-task")
    async def trigger_task(request: Request):
        data = await request.json()
        task_name = data["task"]
        params = data.get("params", {})
        if task_name not in TASK_DEFINITIONS:
            raise HTTPException(404, "Geçersiz task ismi")
        task = celery_app.send_task(f"src.worker.tasks.{task_name}", kwargs=params)
        return JSONResponse({"task_id": task.id})

    @app.post("/admin/api/schedule-task")
    async def schedule_task(request: Request):
        data = await request.json()
        entry = RedBeatSchedulerEntry(
            name=data["name"],
            task=f"src.worker.tasks.{data['task']}",
            schedule=int(data["interval"]),
            kwargs=data.get("params", {}),
            app=celery_app
        )
        entry.save()
        return JSONResponse({"status": "scheduled"})

    @app.get("/admin/api/scheduled-tasks")
    async def list_schedules():
        return [
            {
                "name": entry.name,
                "task": entry.task,
                "interval": entry.schedule.run_every.total_seconds(),
                "params": entry.kwargs
            }
            for entry in RedBeatSchedulerEntry.get_all(celery_app)
        ]

    @app.delete("/admin/api/delete-schedule/{name}")
    async def delete_schedule(name: str):
        try:
            entry = RedBeatSchedulerEntry.from_key(name, app=celery_app)
            entry.delete()
            return JSONResponse({"status": "deleted"})
        except Exception as e:
            raise HTTPException(500, f"Silme hatası: {str(e)}")
from celery.result import AsyncResult
from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import JSONResponse
from .celery_app import celery_app

class CeleryTaskView(BaseView):
    name = "Celery Tasks"
    icon = "fa-solid fa-list-check"
    template = "celery_tasks.html"

    @expose("/tasks", methods=["GET"])
    async def task_list(self, request: Request):
        inspector = celery_app.control.inspect()
        tasks = []

        active = inspector.active() or {}
        scheduled = inspector.scheduled() or {}
        reserved = inspector.reserved() or {}

        for worker, active_tasks in active.items():
            for task in active_tasks:
                result = AsyncResult(task["id"], app=celery_app)
                tasks.append({"type": "Active", "worker": worker, "task": task, "result": result})

        for worker, scheduled_tasks in scheduled.items():
            for task in scheduled_tasks:
                tasks.append({"type": "Scheduled", "worker": worker, "task": task})

        for worker, reserved_tasks in reserved.items():
            for task in reserved_tasks:
                tasks.append({"type": "Reserved", "worker": worker, "task": task})

        return await self.templates.render(
            request, self.template, context={"tasks": tasks}
        )

    @expose("/tasks/revoke/{task_id}", methods=["POST"], in_menu=False)
    async def revoke_task(self, request: Request):
        task_id = request.path_params["task_id"]
        celery_app.control.revoke(task_id, terminate=True)
        return JSONResponse({"status": "OK"})

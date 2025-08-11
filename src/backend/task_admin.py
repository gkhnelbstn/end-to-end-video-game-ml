"""
Task Management Admin Views for SQLAdmin integration.

This module provides admin interface views for managing periodic tasks
through the SQLAdmin interface.
"""

from typing import Any, Dict, List
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from sqladmin import BaseView
from wtforms import Form, StringField, TextAreaField, SelectField, BooleanField, FieldList, FormField
from wtforms.validators import DataRequired, Optional
import json

from .task_scheduler import task_scheduler, TaskConfig

class TaskManagementView(BaseView):
    """Admin view for managing periodic tasks."""
    
    name = "Task Management"
    icon = "fa-solid fa-clock"
    identity = "task_management"  # Required for SQLAdmin routing
    
    async def list(self, request: Request) -> Response:
        """Display list of all scheduled tasks."""
        try:
            tasks = task_scheduler.get_tasks()
            context = {
                "request": request,
                "tasks": tasks,
                "available_functions": task_scheduler.get_available_task_functions()
            }
            return self.templates.TemplateResponse("task_management/list.html", context)
        except Exception as e:
            context = {
                "request": request,
                "error": f"Failed to load tasks: {str(e)}",
                "tasks": [],
                "available_functions": []
            }
            return self.templates.TemplateResponse("task_management/list.html", context)
    
    async def create(self, request: Request) -> Response:
        """Create a new task."""
        if request.method == "GET":
            context = {
                "request": request,
                "available_functions": task_scheduler.get_available_task_functions(),
                "trigger_types": ["interval", "cron"],
                "examples": self._get_example_configs()
            }
            return self.templates.TemplateResponse("task_management/create.html", context)
        
        elif request.method == "POST":
            form_data = await request.form()
            try:
                # Parse form data
                task_config = self._parse_task_form(form_data)
                
                # Add task
                success = await task_scheduler.add_task(task_config)
                
                if success:
                    return RedirectResponse(url="/admin/task-management", status_code=302)
                else:
                    raise Exception("Failed to create task")
                    
            except Exception as e:
                context = {
                    "request": request,
                    "error": f"Failed to create task: {str(e)}",
                    "available_functions": task_scheduler.get_available_task_functions(),
                    "trigger_types": ["interval", "cron"],
                    "examples": self._get_example_configs(),
                    "form_data": dict(form_data)
                }
                return self.templates.TemplateResponse("task_management/create.html", context)
    
    async def edit(self, request: Request) -> Response:
        """Edit an existing task."""
        task_id = request.path_params.get("pk")
        
        if request.method == "GET":
            try:
                task = task_scheduler.get_task(task_id)
                if not task:
                    return RedirectResponse(url="/admin/task-management", status_code=302)
                
                context = {
                    "request": request,
                    "task": task,
                    "task_id": task_id,
                    "available_functions": task_scheduler.get_available_task_functions(),
                    "trigger_types": ["interval", "cron"],
                    "examples": self._get_example_configs()
                }
                return self.templates.TemplateResponse("task_management/edit.html", context)
                
            except Exception as e:
                context = {
                    "request": request,
                    "error": f"Failed to load task: {str(e)}"
                }
                return self.templates.TemplateResponse("task_management/error.html", context)
        
        elif request.method == "POST":
            form_data = await request.form()
            try:
                # Parse form data
                task_config = self._parse_task_form(form_data)
                task_config.id = task_id
                
                # Update task
                success = await task_scheduler.modify_task(task_id, task_config)
                
                if success:
                    return RedirectResponse(url="/admin/task-management", status_code=302)
                else:
                    raise Exception("Failed to update task")
                    
            except Exception as e:
                task = task_scheduler.get_task(task_id)
                context = {
                    "request": request,
                    "error": f"Failed to update task: {str(e)}",
                    "task": task,
                    "task_id": task_id,
                    "available_functions": task_scheduler.get_available_task_functions(),
                    "trigger_types": ["interval", "cron"],
                    "examples": self._get_example_configs(),
                    "form_data": dict(form_data)
                }
                return self.templates.TemplateResponse("task_management/edit.html", context)
    
    async def delete(self, request: Request) -> Response:
        """Delete a task."""
        task_id = request.path_params.get("pk")
        
        try:
            success = await task_scheduler.remove_task(task_id)
            if not success:
                raise Exception("Task not found or could not be deleted")
        except Exception as e:
            # Handle error - could redirect with error message
            pass
        
        return RedirectResponse(url="/admin/task-management", status_code=302)
    
    async def pause_task(self, request: Request) -> Response:
        """Pause a task."""
        task_id = request.path_params.get("pk")
        
        try:
            await task_scheduler.pause_task(task_id)
        except Exception as e:
            # Handle error
            pass
        
        return RedirectResponse(url="/admin/task-management", status_code=302)
    
    async def resume_task(self, request: Request) -> Response:
        """Resume a task."""
        task_id = request.path_params.get("pk")
        
        try:
            await task_scheduler.resume_task(task_id)
        except Exception as e:
            # Handle error
            pass
        
        return RedirectResponse(url="/admin/task-management", status_code=302)
    
    async def execute_task(self, request: Request) -> Response:
        """Execute a task immediately."""
        task_id = request.path_params.get("pk")
        
        try:
            task_config = task_scheduler.task_configs.get(task_id)
            if task_config:
                task_func = task_scheduler.available_tasks.get(task_config.task_function)
                if task_func:
                    result_id = task_scheduler._execute_celery_task(
                        task_func, task_config.args, task_config.kwargs
                    )
        except Exception as e:
            # Handle error
            pass
        
        return RedirectResponse(url="/admin/task-management", status_code=302)
    
    def _parse_task_form(self, form_data: Dict) -> TaskConfig:
        """Parse form data into TaskConfig object."""
        try:
            # Parse trigger config from JSON string
            trigger_config_str = form_data.get("trigger_config", "{}")
            trigger_config = json.loads(trigger_config_str) if trigger_config_str else {}
            
            # Parse args from JSON string
            args_str = form_data.get("args", "[]")
            args = json.loads(args_str) if args_str else []
            
            # Parse kwargs from JSON string
            kwargs_str = form_data.get("kwargs", "{}")
            kwargs = json.loads(kwargs_str) if kwargs_str else {}
            
            return TaskConfig(
                id=form_data.get("id", ""),
                name=form_data.get("name", ""),
                task_function=form_data.get("task_function", ""),
                trigger_type=form_data.get("trigger_type", "interval"),
                trigger_config=trigger_config,
                args=args,
                kwargs=kwargs,
                enabled=form_data.get("enabled") == "on",
                description=form_data.get("description", "")
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in form fields: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to parse form data: {str(e)}")
    
    def _get_example_configs(self) -> Dict[str, Any]:
        """Get example configurations for different trigger types."""
        return {
            "interval_seconds": '{"seconds": 30}',
            "interval_minutes": '{"minutes": 5}',
            "interval_hours": '{"hours": 1}',
            "cron_daily": '{"hour": 9, "minute": 0}',
            "cron_weekly": '{"day_of_week": "mon", "hour": 9, "minute": 0}',
            "cron_monthly": '{"day": 1, "hour": 2, "minute": 0}',
            "args_example": '[10, 20, "parameter"]',
            "kwargs_example": '{"param1": "value1", "param2": 42}'
        }

# Custom routes for task actions
def setup_task_management_routes(admin):
    """Setup custom routes for task management actions."""
    
    @admin.app.get("/admin/task-management")
    async def task_list(request: Request):
        view = TaskManagementView()
        view.templates = admin.templates
        return await view.list(request)
    
    @admin.app.get("/admin/task-management/create")
    @admin.app.post("/admin/task-management/create")
    async def task_create(request: Request):
        view = TaskManagementView()
        view.templates = admin.templates
        return await view.create(request)
    
    @admin.app.get("/admin/task-management/{pk}/edit")
    @admin.app.post("/admin/task-management/{pk}/edit")
    async def task_edit(request: Request):
        view = TaskManagementView()
        view.templates = admin.templates
        return await view.edit(request)
    
    @admin.app.post("/admin/task-management/{pk}/delete")
    async def task_delete(request: Request):
        view = TaskManagementView()
        view.templates = admin.templates
        return await view.delete(request)
    
    @admin.app.post("/admin/task-management/{pk}/pause")
    async def task_pause(request: Request):
        view = TaskManagementView()
        view.templates = admin.templates
        return await view.pause_task(request)
    
    @admin.app.post("/admin/task-management/{pk}/resume")
    async def task_resume(request: Request):
        view = TaskManagementView()
        view.templates = admin.templates
        return await view.resume_task(request)
    
    @admin.app.post("/admin/task-management/{pk}/execute")
    async def task_execute(request: Request):
        view = TaskManagementView()
        view.templates = admin.templates
        return await view.execute_task(request)

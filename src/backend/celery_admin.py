from celery.result import AsyncResult
from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from .celery_app import celery_app
import logging
import json
import importlib

logger = logging.getLogger(__name__)


class CeleryMonitoringView(BaseView):
    name = "Celery Monitoring"
    icon = "fa-solid fa-chart-line"
    category = "Tasks"
    menu_icon = "fa-solid fa-chart-line"

    def _get_available_tasks(self):
        """Mevcut task'ları listele"""
        tasks = {}
        for task_name, task_obj in celery_app.tasks.items():
            if not task_name.startswith('celery.'):  # Built-in task'ları filtrele
                try:
                    # Task'ın modülünü ve fonksiyonunu al
                    module_name = task_obj.__module__
                    func_name = task_obj.__name__

                    # Docstring'i al
                    doc = task_obj.__doc__ or "No description available"

                    # Task'ın parametrelerini almaya çalış
                    import inspect
                    try:
                        sig = inspect.signature(task_obj.run)
                        params = []
                        for param_name, param in sig.parameters.items():
                            if param_name not in ['self', 'args', 'kwargs']:
                                param_info = {
                                    'name': param_name,
                                    'default': param.default if param.default != param.empty else None,
                                    'annotation': str(param.annotation) if param.annotation != param.empty else 'Any'
                                }
                                params.append(param_info)
                    except:
                        params = []

                    tasks[task_name] = {
                        'name': task_name,
                        'func_name': func_name,
                        'module': module_name,
                        'description': doc.strip().split('\n')[0][:100],
                        'full_description': doc.strip(),
                        'parameters': params
                    }
                except Exception as e:
                    logger.warning(f"Could not get info for task {task_name}: {e}")
                    tasks[task_name] = {
                        'name': task_name,
                        'description': 'Task information unavailable',
                        'parameters': []
                    }

        return tasks

    @expose("/tasks", methods=["GET"])
    async def task_list(self, request: Request):
        """Ana task listesi sayfası"""
        tasks = []
        error_message = None

        try:
            inspector = celery_app.control.inspect()

            # Inspector'dan veri almaya çalış
            active = inspector.active() or {}
            scheduled = inspector.scheduled() or {}
            reserved = inspector.reserved() or {}

            # Active tasks
            for worker, active_tasks in active.items():
                if active_tasks:
                    for task in active_tasks:
                        try:
                            result = AsyncResult(task["id"], app=celery_app)
                            tasks.append({
                                "type": "Active",
                                "worker": worker,
                                "task": task,
                                "result": result
                            })
                        except Exception as e:
                            logger.error(f"Error processing active task {task.get('id', 'unknown')}: {e}")

            # Scheduled tasks
            for worker, scheduled_tasks in scheduled.items():
                if scheduled_tasks:
                    for task in scheduled_tasks:
                        tasks.append({
                            "type": "Scheduled",
                            "worker": worker,
                            "task": task,
                            "result": None
                        })

            # Reserved tasks
            for worker, reserved_tasks in reserved.items():
                if reserved_tasks:
                    for task in reserved_tasks:
                        tasks.append({
                            "type": "Reserved",
                            "worker": worker,
                            "task": task,
                            "result": None
                        })

        except Exception as e:
            logger.error(f"Error connecting to Celery: {e}")
            error_message = f"Could not connect to Celery workers: {str(e)}"
            tasks = []

        # Mevcut task türlerini al
        available_tasks = self._get_available_tasks()

        context = {
            "tasks": tasks,
            "available_tasks": available_tasks,
            "error_message": error_message,
            "worker_count": len(set(task["worker"] for task in tasks)) if tasks else 0
        }

        return self._create_advanced_response(context)

    @expose("/tasks/run", methods=["GET", "POST"])
    async def run_task(self, request: Request):
        """Task çalıştırma sayfası"""
        if request.method == "GET":
            available_tasks = self._get_available_tasks()
            task_name = request.query_params.get("task")
            selected_task = available_tasks.get(task_name) if task_name else None

            return self._create_run_task_form(available_tasks, selected_task)

        elif request.method == "POST":
            form = await request.form()
            task_name = form.get("task_name")

            if not task_name:
                return JSONResponse({"error": "Task name is required"}, status_code=400)

            try:
                # Task'ı al
                task = celery_app.tasks.get(task_name)
                if not task:
                    return JSONResponse({"error": f"Task {task_name} not found"}, status_code=404)

                # Parametreleri hazırla
                args = []
                kwargs = {}

                # Form'dan parametreleri al
                for key, value in form.items():
                    if key.startswith("param_"):
                        param_name = key.replace("param_", "")
                        # Basit tip dönüşümü
                        try:
                            if value.lower() in ['true', 'false']:
                                value = value.lower() == 'true'
                            elif value.isdigit():
                                value = int(value)
                            elif '.' in value and value.replace('.', '').isdigit():
                                value = float(value)
                        except:
                            pass
                        kwargs[param_name] = value

                # Task'ı çalıştır
                result = task.delay(**kwargs)

                return JSONResponse({
                    "success": True,
                    "task_id": result.id,
                    "message": f"Task {task_name} started successfully"
                })

            except Exception as e:
                logger.error(f"Error running task {task_name}: {e}")
                return JSONResponse({"error": str(e)}, status_code=500)

    @expose("/tasks/status/{task_id}", methods=["GET"])
    async def task_status(self, request: Request):
        """Task durumu API"""
        task_id = request.path_params["task_id"]

        try:
            result = AsyncResult(task_id, app=celery_app)

            response_data = {
                "task_id": task_id,
                "status": result.status,
                "result": result.result if result.ready() else None,
                "info": result.info,
                "traceback": result.traceback if result.failed() else None
            }

            return JSONResponse(response_data)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @expose("/tasks/revoke/{task_id}", methods=["POST"])
    async def revoke_task(self, request: Request):
        task_id = request.path_params["task_id"]

        if not task_id:
            return JSONResponse({"error": "Task ID is required"}, status_code=400)

        try:
            celery_app.control.revoke(task_id, terminate=True)
            return JSONResponse({"success": True, "message": f"Task {task_id} revoked"})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    def _create_run_task_form(self, available_tasks, selected_task=None):
        """Task çalıştırma formu oluştur"""
        task_options = ""
        for task_name, task_info in available_tasks.items():
            selected = "selected" if selected_task and selected_task["name"] == task_name else ""
            task_options += f'<option value="{task_name}" {selected}>{task_name}</option>'

        param_fields = ""
        if selected_task and selected_task.get("parameters"):
            for param in selected_task["parameters"]:
                default_value = param.get("default", "")
                if default_value is None:
                    default_value = ""
                param_fields += f"""
                <div class="param-field">
                    <label>{param["name"]} ({param["annotation"]}):</label>
                    <input type="text" name="param_{param["name"]}" value="{default_value}" 
                           placeholder="Enter {param["name"]}">
                </div>
                """

        task_description = ""
        if selected_task:
            task_description = f"""
            <div class="task-description">
                <h4>Description:</h4>
                <p>{selected_task.get("full_description", "No description available")}</p>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Run Celery Task</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
                .form-group {{ margin-bottom: 15px; }}
                label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
                select, input, textarea {{ width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }}
                button {{ background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }}
                button:hover {{ background: #0056b3; }}
                .param-field {{ margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 4px; }}
                .task-description {{ margin: 15px 0; padding: 15px; background: #e9ecef; border-radius: 4px; }}
                .back-btn {{ background: #6c757d; margin-right: 10px; }}
                .result {{ margin-top: 20px; padding: 15px; border-radius: 4px; }}
                .success {{ background: #d4edda; color: #155724; }}
                .error {{ background: #f8d7da; color: #721c24; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Run Celery Task</h1>

                <button class="back-btn" onclick="window.location.href='/admin/tasks'">← Back to Task List</button>

                <form id="taskForm" method="post">
                    <div class="form-group">
                        <label for="task_name">Select Task:</label>
                        <select name="task_name" id="task_name" onchange="updateTaskForm()">
                            <option value="">Select a task...</option>
                            {task_options}
                        </select>
                    </div>

                    {task_description}

                    <div id="parameters">
                        {param_fields}
                    </div>

                    <button type="submit">Run Task</button>
                </form>

                <div id="result"></div>
            </div>

            <script>
                function updateTaskForm() {{
                    const taskName = document.getElementById('task_name').value;
                    if (taskName) {{
                        window.location.href = '/admin/tasks/run?task=' + encodeURIComponent(taskName);
                    }}
                }}

                document.getElementById('taskForm').addEventListener('submit', async function(e) {{
                    e.preventDefault();

                    const formData = new FormData(this);
                    const resultDiv = document.getElementById('result');

                    try {{
                        const response = await fetch('/admin/tasks/run', {{
                            method: 'POST',
                            body: formData
                        }});

                        const data = await response.json();

                        if (data.success) {{
                            resultDiv.innerHTML = `
                                <div class="result success">
                                    <strong>Success!</strong> Task started with ID: ${{data.task_id}}
                                    <br><a href="/admin/tasks/status/${{data.task_id}}" target="_blank">Check Status</a>
                                </div>
                            `;
                        }} else {{
                            resultDiv.innerHTML = `
                                <div class="result error">
                                    <strong>Error:</strong> ${{data.error}}
                                </div>
                            `;
                        }}
                    }} catch (error) {{
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <strong>Error:</strong> ${{error.message}}
                            </div>
                        `;
                    }}
                }});
            </script>
        </body>
        </html>
        """

        return HTMLResponse(content=html)

    def _create_advanced_response(self, context):
        """Gelişmiş task listesi sayfası"""
        tasks = context.get("tasks", [])
        available_tasks = context.get("available_tasks", {})
        error_message = context.get("error_message")
        worker_count = context.get("worker_count", 0)

        active_count = len([t for t in tasks if t["type"] == "Active"])
        scheduled_count = len([t for t in tasks if t["type"] == "Scheduled"])

        # Available tasks listesi
        available_tasks_html = ""
        for task_name, task_info in available_tasks.items():
            available_tasks_html += f"""
            <tr>
                <td><strong>{task_name}</strong></td>
                <td>{task_info.get('description', 'No description')}</td>
                <td>{len(task_info.get('parameters', []))}</td>
                <td>
                    <button onclick="runTask('{task_name}')" class="btn-run">Run</button>
                </td>
            </tr>
            """

        # Active tasks listesi
        active_tasks_html = ""
        for task_info in tasks:
            task_name = task_info["task"].get("name", "Unknown")
            task_id = task_info["task"].get("id", "Unknown")
            worker = task_info["worker"]
            task_type = task_info["type"]

            status = "-"
            status_class = ""
            if task_info["result"]:
                state = task_info["result"].state
                if state == 'SUCCESS':
                    status = '✓ Success'
                    status_class = 'status-success'
                elif state == 'FAILURE':
                    status = '✗ Failed'
                    status_class = 'status-failed'
                elif state == 'PENDING':
                    status = '⏳ Pending'
                    status_class = 'status-pending'
                else:
                    status = state
                    status_class = 'status-other'

            active_tasks_html += f"""
            <tr>
                <td><span class="task-type {task_type.lower()}">{task_type}</span></td>
                <td><strong>{task_name}</strong></td>
                <td><code class="task-id">{task_id[:8]}...</code></td>
                <td>{worker}</td>
                <td><span class="{status_class}">{status}</span></td>
                <td>
                    <button onclick="checkStatus('{task_id}')" class="btn-status">Status</button>
                    <button onclick="revokeTask('{task_id}')" class="btn-revoke">Revoke</button>
                </td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Celery Tasks Management</title>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1400px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 8px; margin-bottom: 20px; }}
                .stats {{ display: flex; gap: 20px; margin-bottom: 20px; }}
                .stat-card {{ background: white; padding: 20px; border-radius: 8px; text-align: center; flex: 1; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .stat-number {{ font-size: 2rem; font-weight: bold; color: #667eea; }}
                .stat-label {{ color: #6c757d; margin-top: 5px; }}
                .section {{ background: white; margin-bottom: 20px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .section-header {{ background: #f8f9fa; padding: 15px; border-bottom: 1px solid #dee2e6; display: flex; justify-content: between; align-items: center; }}
                .section-title {{ font-size: 1.2rem; font-weight: 600; margin: 0; }}
                .btn-primary {{ background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }}
                .btn-primary:hover {{ background: #0056b3; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
                th {{ background: #f8f9fa; font-weight: 600; }}
                .task-type {{ padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 500; }}
                .task-type.active {{ background: #d4edda; color: #155724; }}
                .task-type.scheduled {{ background: #fff3cd; color: #856404; }}
                .task-type.reserved {{ background: #cce7ff; color: #004085; }}
                .task-id {{ font-family: monospace; font-size: 0.9rem; color: #6c757d; }}
                .btn-run {{ background: #28a745; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; }}
                .btn-status {{ background: #17a2b8; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; margin-right: 5px; }}
                .btn-revoke {{ background: #dc3545; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; }}
                .error-message {{ background: #f8d7da; color: #721c24; padding: 15px; margin: 20px; border-radius: 5px; }}
                .no-tasks {{ text-align: center; padding: 40px; color: #6c757d; }}
                .status-success {{ color: #28a745; }}
                .status-failed {{ color: #dc3545; }}
                .status-pending {{ color: #ffc107; }}
                .refresh-btn {{ position: fixed; bottom: 20px; right: 20px; background: #667eea; color: white; border: none; padding: 15px; border-radius: 50%; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1><i class="fas fa-list-check"></i> Celery Tasks Management</h1>
                    <p>Monitor and control your background tasks</p>
                </div>

                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-number">{len(tasks)}</div>
                        <div class="stat-label">Running Tasks</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{active_count}</div>
                        <div class="stat-label">Active</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{scheduled_count}</div>
                        <div class="stat-label">Scheduled</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{worker_count}</div>
                        <div class="stat-label">Workers</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{len(available_tasks)}</div>
                        <div class="stat-label">Available Tasks</div>
                    </div>
                </div>

                {f'<div class="error-message"><i class="fas fa-exclamation-triangle"></i> <strong>Error:</strong> {error_message}</div>' if error_message else ''}

                <div class="section">
                    <div class="section-header">
                        <h2 class="section-title">Available Tasks</h2>
                        <button class="btn-primary" onclick="window.location.href='/admin/tasks/run'">
                            <i class="fas fa-play"></i> Run New Task
                        </button>
                    </div>
                    {f'<table><thead><tr><th>Task Name</th><th>Description</th><th>Parameters</th><th>Actions</th></tr></thead><tbody>{available_tasks_html}</tbody></table>' if available_tasks else '<div class="no-tasks">No tasks available</div>'}
                </div>

                <div class="section">
                    <div class="section-header">
                        <h2 class="section-title">Running Tasks</h2>
                    </div>
                    {f'<table><thead><tr><th>Type</th><th>Task Name</th><th>Task ID</th><th>Worker</th><th>Status</th><th>Actions</th></tr></thead><tbody>{active_tasks_html}</tbody></table>' if tasks else '<div class="no-tasks">No running tasks</div>'}
                </div>
            </div>

            <button class="refresh-btn" onclick="window.location.reload()" title="Refresh">
                <i class="fas fa-sync-alt"></i>
            </button>

            <script>
                function runTask(taskName) {{
                    window.location.href = '/admin/tasks/run?task=' + encodeURIComponent(taskName);
                }}

                async function checkStatus(taskId) {{
                    try {{
                        const response = await fetch(`/admin/tasks/status/${{taskId}}`);
                        const data = await response.json();
                        alert(`Task Status: ${{data.status}}\\nResult: ${{JSON.stringify(data.result, null, 2)}}`);
                    }} catch (error) {{
                        alert('Error checking status: ' + error.message);
                    }}
                }}

                async function revokeTask(taskId) {{
                    if (confirm('Are you sure you want to revoke this task?')) {{
                        try {{
                            const response = await fetch(`/admin/tasks/revoke/${{taskId}}`, {{ method: 'POST' }});
                            const data = await response.json();
                            if (data.success) {{
                                alert('Task revoked successfully');
                                window.location.reload();
                            }} else {{
                                alert('Error: ' + data.error);
                            }}
                        }} catch (error) {{
                            alert('Error revoking task: ' + error.message);
                        }}
                    }}
                }}

                // Auto-refresh every 10 seconds
                setTimeout(() => window.location.reload(), 10000);
            </script>
        </body>
        </html>
        """

        return HTMLResponse(content=html)
"""
Task Management API endpoints for dynamic periodic task control.

This module provides REST API endpoints to manage periodic tasks:
- Add, remove, pause, resume tasks
- Modify task parameters
- View task status and schedules
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from .task_scheduler import task_scheduler, TaskConfig

# Create router for task management endpoints
router = APIRouter(prefix="/api/tasks", tags=["Task Management"])

class TaskCreateRequest(BaseModel):
    """Request model for creating a new task."""
    id: str = Field(..., description="Unique task identifier")
    name: str = Field(..., description="Human-readable task name")
    task_function: str = Field(..., description="Task function name to execute")
    trigger_type: str = Field(..., description="Trigger type: 'interval' or 'cron'")
    trigger_config: Dict[str, Any] = Field(..., description="Trigger configuration")
    args: List[Any] = Field(default=[], description="Task arguments")
    kwargs: Dict[str, Any] = Field(default={}, description="Task keyword arguments")
    enabled: bool = Field(default=True, description="Whether task is enabled")
    description: Optional[str] = Field(default=None, description="Task description")

class TaskUpdateRequest(BaseModel):
    """Request model for updating an existing task."""
    name: Optional[str] = Field(default=None, description="Human-readable task name")
    task_function: Optional[str] = Field(default=None, description="Task function name to execute")
    trigger_type: Optional[str] = Field(default=None, description="Trigger type: 'interval' or 'cron'")
    trigger_config: Optional[Dict[str, Any]] = Field(default=None, description="Trigger configuration")
    args: Optional[List[Any]] = Field(default=None, description="Task arguments")
    kwargs: Optional[Dict[str, Any]] = Field(default=None, description="Task keyword arguments")
    enabled: Optional[bool] = Field(default=None, description="Whether task is enabled")
    description: Optional[str] = Field(default=None, description="Task description")

class TaskResponse(BaseModel):
    """Response model for task information."""
    id: str
    name: str
    next_run_time: Optional[str]
    trigger: str
    enabled: bool
    description: str
    task_function: str
    args: List[Any]
    kwargs: Dict[str, Any]

class TaskListResponse(BaseModel):
    """Response model for task list."""
    tasks: List[TaskResponse]
    total: int

@router.get("/", response_model=TaskListResponse)
async def list_tasks():
    """Get all scheduled tasks."""
    try:
        tasks = task_scheduler.get_tasks()
        return TaskListResponse(
            tasks=[TaskResponse(**task) for task in tasks],
            total=len(tasks)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {str(e)}")

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get a specific task by ID."""
    try:
        task = task_scheduler.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        return TaskResponse(**task)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")

@router.post("/", response_model=dict)
async def create_task(task_request: TaskCreateRequest):
    """Create a new scheduled task."""
    try:
        task_config = TaskConfig(**task_request.dict())
        success = await task_scheduler.add_task(task_config)
        
        if success:
            return {"message": f"Task '{task_request.id}' created successfully", "task_id": task_request.id}
        else:
            raise HTTPException(status_code=400, detail=f"Failed to create task '{task_request.id}'")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")

@router.put("/{task_id}", response_model=dict)
async def update_task(task_id: str, task_request: TaskUpdateRequest):
    """Update an existing task."""
    try:
        # Get current task
        current_task = task_scheduler.get_task(task_id)
        if not current_task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        
        # Merge updates with current configuration
        current_config = task_scheduler.task_configs.get(task_id)
        if not current_config:
            raise HTTPException(status_code=404, detail=f"Task configuration for '{task_id}' not found")
        
        # Update only provided fields
        update_data = task_request.dict(exclude_unset=True)
        updated_config_data = current_config.dict()
        updated_config_data.update(update_data)
        
        new_config = TaskConfig(**updated_config_data)
        success = await task_scheduler.modify_task(task_id, new_config)
        
        if success:
            return {"message": f"Task '{task_id}' updated successfully"}
        else:
            raise HTTPException(status_code=400, detail=f"Failed to update task '{task_id}'")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update task: {str(e)}")

@router.delete("/{task_id}", response_model=dict)
async def delete_task(task_id: str):
    """Delete a scheduled task."""
    try:
        success = await task_scheduler.remove_task(task_id)
        if success:
            return {"message": f"Task '{task_id}' deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {str(e)}")

@router.post("/{task_id}/pause", response_model=dict)
async def pause_task(task_id: str):
    """Pause a scheduled task."""
    try:
        success = await task_scheduler.pause_task(task_id)
        if success:
            return {"message": f"Task '{task_id}' paused successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause task: {str(e)}")

@router.post("/{task_id}/resume", response_model=dict)
async def resume_task(task_id: str):
    """Resume a paused task."""
    try:
        success = await task_scheduler.resume_task(task_id)
        if success:
            return {"message": f"Task '{task_id}' resumed successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume task: {str(e)}")

@router.get("/functions/available", response_model=dict)
async def get_available_functions():
    """Get list of available task functions."""
    try:
        functions = task_scheduler.get_available_task_functions()
        return {
            "functions": functions,
            "total": len(functions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available functions: {str(e)}")

@router.post("/{task_id}/execute", response_model=dict)
async def execute_task_now(task_id: str):
    """Execute a task immediately (one-time execution)."""
    try:
        task = task_scheduler.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        
        task_config = task_scheduler.task_configs.get(task_id)
        if not task_config:
            raise HTTPException(status_code=404, detail=f"Task configuration for '{task_id}' not found")
        
        # Get the task function
        task_func = task_scheduler.available_tasks.get(task_config.task_function)
        if not task_func:
            raise HTTPException(status_code=400, detail=f"Task function '{task_config.task_function}' not available")
        
        # Execute immediately
        result_id = task_scheduler._execute_celery_task(task_func, task_config.args, task_config.kwargs)
        
        return {
            "message": f"Task '{task_id}' executed successfully",
            "celery_task_id": result_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute task: {str(e)}")

# Example configurations for documentation
@router.get("/examples/configurations", response_model=dict)
async def get_example_configurations():
    """Get example task configurations for different trigger types."""
    examples = {
        "interval_example": {
            "id": "example_interval_task",
            "name": "Example Interval Task",
            "task_function": "example_task",
            "trigger_type": "interval",
            "trigger_config": {
                "seconds": 30  # Every 30 seconds
            },
            "args": [10, 20],
            "kwargs": {"param": "value"},
            "enabled": True,
            "description": "Example task that runs every 30 seconds"
        },
        "cron_example": {
            "id": "example_cron_task",
            "name": "Example Cron Task",
            "task_function": "example_task",
            "trigger_type": "cron",
            "trigger_config": {
                "hour": 9,
                "minute": 0,
                "day_of_week": "mon-fri"  # Weekdays at 9:00 AM
            },
            "args": [],
            "kwargs": {},
            "enabled": True,
            "description": "Example task that runs weekdays at 9:00 AM"
        },
        "monthly_example": {
            "id": "monthly_report_task",
            "name": "Monthly Report Task",
            "task_function": "fetch_monthly_updates",
            "trigger_type": "cron",
            "trigger_config": {
                "day": 1,
                "hour": 2,
                "minute": 0  # 1st of every month at 2:00 AM
            },
            "args": [],
            "kwargs": {},
            "enabled": True,
            "description": "Monthly report generation task"
        }
    }
    
    return {
        "examples": examples,
        "trigger_types": {
            "interval": "Use for tasks that repeat at regular intervals (seconds, minutes, hours, days)",
            "cron": "Use for tasks that run at specific times (like cron jobs)"
        },
        "available_functions": task_scheduler.get_available_task_functions()
    }

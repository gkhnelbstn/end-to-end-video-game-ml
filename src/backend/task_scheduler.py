"""
Dynamic Task Scheduler using APScheduler for periodic task management.

This module provides functionality to dynamically add, remove, pause, resume
and manage periodic tasks that can be controlled via API endpoints.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from pydantic import BaseModel

# Import Celery tasks
from src.worker.tasks import (
    fetch_monthly_updates_task,
    fetch_weekly_updates_task,
    example_task
)

logger = logging.getLogger(__name__)

class TaskConfig(BaseModel):
    """Configuration model for scheduled tasks."""
    id: str
    name: str
    task_function: str
    trigger_type: str  # 'interval' or 'cron'
    trigger_config: Dict[str, Any]
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}
    enabled: bool = True
    description: Optional[str] = None

class DynamicTaskScheduler:
    """Dynamic task scheduler using APScheduler."""
    
    def __init__(self):
        """Initialize the scheduler with proper configuration."""
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': ThreadPoolExecutor(20)
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults
        )
        
        # Available task functions mapping
        self.available_tasks = {
            'fetch_monthly_updates': fetch_monthly_updates_task,
            'fetch_weekly_updates': fetch_weekly_updates_task,
            'example_task': example_task
        }
        
        # Add event listeners
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
        
        # Store task configurations
        self.task_configs: Dict[str, TaskConfig] = {}
    
    async def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Dynamic task scheduler started")
            
            # Add default tasks
            await self._add_default_tasks()
    
    async def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Dynamic task scheduler stopped")
    
    async def _add_default_tasks(self):
        """Add default periodic tasks."""
        default_tasks = [
            TaskConfig(
                id="monthly_updates",
                name="Monthly Game Updates",
                task_function="fetch_monthly_updates",
                trigger_type="cron",
                trigger_config={"day": 1, "hour": 0, "minute": 0},
                description="Fetch monthly game updates on the 1st of each month"
            ),
            TaskConfig(
                id="weekly_updates", 
                name="Weekly Game Updates",
                task_function="fetch_weekly_updates",
                trigger_type="cron",
                trigger_config={"day_of_week": "mon", "hour": 0, "minute": 0},
                description="Fetch weekly game updates every Monday"
            )
        ]
        
        for task_config in default_tasks:
            await self.add_task(task_config)
    
    async def add_task(self, task_config: TaskConfig) -> bool:
        """Add a new scheduled task."""
        try:
            if task_config.task_function not in self.available_tasks:
                raise ValueError(f"Task function '{task_config.task_function}' not available")
            
            task_func = self.available_tasks[task_config.task_function]
            
            # Create trigger based on type
            if task_config.trigger_type == "interval":
                trigger = IntervalTrigger(**task_config.trigger_config)
            elif task_config.trigger_type == "cron":
                trigger = CronTrigger(**task_config.trigger_config)
            else:
                raise ValueError(f"Unsupported trigger type: {task_config.trigger_type}")
            
            # Add job to scheduler
            self.scheduler.add_job(
                func=self._execute_celery_task,
                trigger=trigger,
                id=task_config.id,
                name=task_config.name,
                args=[task_func, task_config.args, task_config.kwargs],
                replace_existing=True
            )
            
            # Store configuration
            self.task_configs[task_config.id] = task_config
            
            # Pause if not enabled
            if not task_config.enabled:
                await self.pause_task(task_config.id)
            
            logger.info(f"Task '{task_config.id}' added successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add task '{task_config.id}': {e}")
            return False
    
    async def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task."""
        try:
            self.scheduler.remove_job(task_id)
            if task_id in self.task_configs:
                del self.task_configs[task_id]
            logger.info(f"Task '{task_id}' removed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to remove task '{task_id}': {e}")
            return False
    
    async def pause_task(self, task_id: str) -> bool:
        """Pause a scheduled task."""
        try:
            self.scheduler.pause_job(task_id)
            if task_id in self.task_configs:
                self.task_configs[task_id].enabled = False
            logger.info(f"Task '{task_id}' paused successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to pause task '{task_id}': {e}")
            return False
    
    async def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        try:
            self.scheduler.resume_job(task_id)
            if task_id in self.task_configs:
                self.task_configs[task_id].enabled = True
            logger.info(f"Task '{task_id}' resumed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to resume task '{task_id}': {e}")
            return False
    
    async def modify_task(self, task_id: str, task_config: TaskConfig) -> bool:
        """Modify an existing task."""
        try:
            # Remove old task
            await self.remove_task(task_id)
            # Add new task with same ID
            task_config.id = task_id
            return await self.add_task(task_config)
        except Exception as e:
            logger.error(f"Failed to modify task '{task_id}': {e}")
            return False
    
    def get_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks with their status."""
        tasks = []
        for job in self.scheduler.get_jobs():
            task_config = self.task_configs.get(job.id, {})
            # Check if job is paused by looking at next_run_time and task_config
            is_enabled = job.next_run_time is not None and getattr(task_config, 'enabled', True)
            tasks.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "enabled": is_enabled,
                "description": getattr(task_config, 'description', ''),
                "task_function": getattr(task_config, 'task_function', ''),
                "args": getattr(task_config, 'args', []),
                "kwargs": getattr(task_config, 'kwargs', {})
            })
        return tasks
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task by ID."""
        try:
            job = self.scheduler.get_job(task_id)
            if job:
                task_config = self.task_configs.get(task_id, {})
                is_enabled = job.next_run_time is not None and getattr(task_config, 'enabled', True)
                return {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                    "enabled": is_enabled,
                    "description": getattr(task_config, 'description', ''),
                    "task_function": getattr(task_config, 'task_function', ''),
                    "args": getattr(task_config, 'args', []),
                    "kwargs": getattr(task_config, 'kwargs', {})
                }
        except Exception as e:
            logger.error(f"Failed to get task '{task_id}': {e}")
        return None
    
    def get_available_task_functions(self) -> List[str]:
        """Get list of available task functions."""
        return list(self.available_tasks.keys())
    
    def _execute_celery_task(self, task_func, args: List, kwargs: Dict):
        """Execute a Celery task asynchronously."""
        try:
            # Use Celery's delay method to execute task asynchronously
            result = task_func.delay(*args, **kwargs)
            logger.info(f"Celery task executed with ID: {result.id}")
            return result.id
        except Exception as e:
            logger.error(f"Failed to execute Celery task: {e}")
            raise
    
    def _job_executed(self, event):
        """Handle job execution events."""
        logger.info(f"Job {event.job_id} executed successfully")
    
    def _job_error(self, event):
        """Handle job error events."""
        logger.error(f"Job {event.job_id} crashed: {event.exception}")

# Global scheduler instance
task_scheduler = DynamicTaskScheduler()

from celery import shared_task
import psutil
from ..models import LLMLog, LLMRun, Task
from datetime import timedelta
from django.utils import timezone
from .orchestrator import Orchestrator
import hashlib
import shutil
import os
import subprocess
from .task_manager import TaskManager

@shared_task
def collect_metrics():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    disk_usage = psutil.disk_usage('/')

    LLMLog.objects.create(
        source='monitor_agent',
        level='INFO',
        message='System metrics',
        details={
            'cpu_percent': cpu_percent,
            'memory_percent': memory_info.percent,
            'disk_percent': disk_usage.percent,
        }
    )

@shared_task
def analyze_logs():
    one_hour_ago = timezone.now() - timedelta(hours=1)
    error_logs = LLMLog.objects.filter(level='ERROR', timestamp__gte=one_hour_ago)

    grouped_logs = {}
    for log in error_logs:
        log_hash = hashlib.md5(log.message.encode()).hexdigest()
        if log_hash not in grouped_logs:
            grouped_logs[log_hash] = []
        grouped_logs[log_hash].append(log)

    for log_hash, logs in grouped_logs.items():
        stacktrace = logs[0].message
        plan = Orchestrator.get_fix(stacktrace)

        if plan and plan.get("operations"):
            tmp_dir = f"/tmp/{log_hash}"
            shutil.copytree(".", tmp_dir, ignore=shutil.ignore_patterns('*.pyc', '__pycache__', '.git'))

            # This is a simplified application of the plan. A real implementation
            # would need to be more robust.
            for op in plan.get("operations"):
                TaskManager.apply_op(op, base_dir=tmp_dir)

            try:
                subprocess.run(["docker", "build", "-t", f"django-llm-test:{log_hash}", tmp_dir], check=True)
                result = subprocess.run(["docker", "run", f"django-llm-test:{log_hash}", "python", "manage.py", "test"], capture_output=True, text=True)

                if result.returncode == 0:
                    run = LLMRun.objects.create(
                        prompt=f"Fix for error: {stacktrace[:100]}...",
                        plan=plan,
                        state='PENDING',
                        run_type='AI',
                    )
                    for op in plan.get("operations", []):
                        Task.objects.create(run=run, op=op.get("op"), params=op)
            finally:
                shutil.rmtree(tmp_dir)
                subprocess.run(["docker", "rmi", f"django-llm-test:{log_hash}"])

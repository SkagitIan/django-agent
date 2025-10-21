from django.core.management import call_command
from ..models import LLMRun, Task
from .codemods import Codemods
import os

class TaskManager:
    @staticmethod
    def apply_run(run: LLMRun):
        for op in run.plan.get("operations", []):
            task = Task.objects.create(run=run, op=op.get("op"), params=op)
            print(f"Applying task {task.id}: {task.op} with params {task.params}")
            if task.op == 'create_app':
                app_name = op.get('name')
                call_command('startapp', app_name)
                with open(f"{app_name}/urls.py", "w") as f:
                    f.write("from django.urls import path\nurlpatterns = []\n")
                Codemods.include_url_conf(app_name)
            elif task.op == 'add_model':
                Codemods.add_model(
                    app_name=op.get('app'),
                    model_name=op.get('model'),
                    fields=op.get('fields')
                )
            elif task.op == 'add_view':
                Codemods.add_view(
                    app_name=op.get('app'),
                    view_name=op.get('name')
                )
            elif task.op == 'add_template':
                Codemods.add_template(
                    template_name=op.get('name'),
                    content=op.get('content')
                )
            elif task.op == 'add_url':
                Codemods.add_url(
                    app_name=op.get('app'),
                    url_pattern=op.get('pattern')
                )
            task.status = "APPLIED"
            task.save()

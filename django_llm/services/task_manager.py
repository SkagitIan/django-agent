from django.core.management import call_command
from ..models import LLMRun, Task
from .codemods import Codemods
import os
import difflib
import shutil

class RollbackManager:
    def __init__(self):
        self.backups = {}
        self.created_dirs = []

    def backup_file(self, path):
        if os.path.exists(path):
            self.backups[path] = Codemods.get_original_code(path)

    def add_created_dir(self, path):
        self.created_dirs.append(path)

    def rollback(self):
        for path, content in self.backups.items():
            with open(path, "w") as f:
                f.write(content)
        for path in self.created_dirs:
            if os.path.exists(path):
                shutil.rmtree(path)

class TaskManager:
    @staticmethod
    def apply_run(run: LLMRun, dry_run=False):
        rollback_manager = RollbackManager()
        try:
            for op in run.plan.get("operations", []):
                task = Task.objects.create(run=run, op=op.get("op"), params=op)

                if dry_run:
                    diff = TaskManager.generate_diff(op)
                    task.diff = diff
                    task.save()
                else:
                    TaskManager.apply_op(op, rollback_manager)
                    task.status = "APPLIED"
                    task.save()
        except Exception as e:
            rollback_manager.rollback()
            raise e

    @staticmethod
    def apply_op(op: dict, rollback_manager: RollbackManager = None, base_dir="."):
        if rollback_manager:
            path = TaskManager.get_path_for_op(op, base_dir=base_dir)
            if path:
                rollback_manager.backup_file(path)

        print(f"Applying op: {op.get('op')} with params {op}")
        if op.get("op") == 'create_app':
            app_name = op.get('name')
            # The startapp command does not support a base_dir argument, so we have to chdir
            original_dir = os.getcwd()
            os.chdir(base_dir)
            call_command('startapp', app_name)
            os.chdir(original_dir)

            if rollback_manager:
                rollback_manager.add_created_dir(os.path.join(base_dir, app_name))

            with open(os.path.join(base_dir, app_name, "urls.py"), "w") as f:
                f.write("from django.urls import path\nurlpatterns = []\n")
            Codemods.include_url_conf(app_name, base_dir=base_dir)
        elif op.get("op") == 'add_model':
            app_name = op.get('app')
            model_name = op.get('model')
            fields = op.get('fields')
            Codemods.add_model(app_name, model_name, fields, base_dir=base_dir)
            Codemods.register_model_admin(app_name, model_name, base_dir=base_dir)
        elif op.get("op") == 'add_form':
            Codemods.add_form(
                app_name=op.get('app'),
                model_name=op.get('model'),
                base_dir=base_dir
            )
        elif op.get("op") == 'add_view':
            Codemods.add_view(
                app_name=op.get('app'),
                view_name=op.get('name'),
                view_type=op.get('view_type'),
                model=op.get('model'),
                form_class=op.get('form_class'),
                success_url=op.get('success_url'),
                base_dir=base_dir
            )
        elif op.get("op") == 'add_template':
            Codemods.add_template(
                template_name=op.get('name'),
                content=op.get('content'),
                base_dir=base_dir
            )
        elif op.get("op") == 'add_url':
            Codemods.add_url(
                app_name=op.get('app'),
                url_pattern=op.get('pattern'),
                base_dir=base_dir
            )


    @staticmethod
    def get_path_for_op(op: dict, base_dir=".") -> str | None:
        if op.get("op") == "add_model":
            return Codemods._get_models_path(op.get("app"), base_dir=base_dir)
        elif op.get("op") == "add_form":
            return Codemods._get_forms_path(op.get("app"), base_dir=base_dir)
        elif op.get("op") == "add_view":
            return Codemods._get_views_path(op.get("app"), base_dir=base_dir)
        elif op.get("op") == "add_template":
            return Codemods._get_template_path(op.get("name"), base_dir=base_dir)
        elif op.get("op") == "add_url":
            return Codemods._get_urls_path(op.get("app"), base_dir=base_dir)
        elif op.get("op") == "include_url_conf":
            return Codemods._get_project_urls_path(base_dir=base_dir)
        return None


    @staticmethod
    def generate_diff(op: dict) -> str:
        if op.get("op") == "add_model":
            app_name = op.get("app")
            model_name = op.get("model")
            fields = op.get("fields")

            original_code = Codemods.get_original_code(Codemods._get_models_path(app_name))
            modified_code = Codemods.add_model(app_name, model_name, fields, dry_run=True)

            diff = difflib.unified_diff(
                original_code.splitlines(keepends=True),
                modified_code.splitlines(keepends=True),
                fromfile='before',
                tofile='after',
            )
            return "".join(diff)
        elif op.get("op") == "add_form":
            app_name = op.get("app")
            model_name = op.get("model")

            original_code = ""
            if os.path.exists(Codemods._get_forms_path(app_name)):
                original_code = Codemods.get_original_code(Codemods._get_forms_path(app_name))

            modified_code = Codemods.add_form(app_name, model_name, dry_run=True)

            diff = difflib.unified_diff(
                original_code.splitlines(keepends=True),
                modified_code.splitlines(keepends=True),
                fromfile='before',
                tofile='after',
            )
            return "".join(diff)
        elif op.get("op") == "add_view":
            app_name = op.get("app")
            view_name = op.get("name")
            view_type = op.get("view_type")
            model = op.get("model")
            form_class = op.get("form_class")
            success_url = op.get("success_url")

            original_code = Codemods.get_original_code(Codemods._get_views_path(app_name))
            modified_code = Codemods.add_view(app_name, view_name, view_type, model, form_class, success_url, dry_run=True)

            diff = difflib.unified_diff(
                original_code.splitlines(keepends=True),
                modified_code.splitlines(keepends=True),
                fromfile='before',
                tofile='after',
            )
            return "".join(diff)
        elif op.get("op") == "add_template":
            template_name = op.get("name")
            content = op.get("content")

            original_code = ""
            if os.path.exists(Codemods._get_template_path(template_name)):
                original_code = Codemods.get_original_code(Codemods._get_template_path(template_name))

            modified_code = Codemods.add_template(template_name, content, dry_run=True)

            diff = difflib.unified_diff(
                original_code.splitlines(keepends=True),
                modified_code.splitlines(keepends=True),
                fromfile='before',
                tofile='after',
            )
            return "".join(diff)
        elif op.get("op") == "add_url":
            app_name = op.get("app")
            url_pattern = op.get("pattern")

            original_code = Codemods.get_original_code(Codemods._get_urls_path(app_name))
            modified_code = Codemods.add_url(app_name, url_pattern, dry_run=True)

            diff = difflib.unified_diff(
                original_code.splitlines(keepends=True),
                modified_code.splitlines(keepends=True),
                fromfile='before',
                tofile='after',
            )
            return "".join(diff)
        elif op.get("op") == "create_app":
            app_name = op.get("name")
            return f"--- a/{app_name}\n+++ b/{app_name}\nnew directory"
        return ""

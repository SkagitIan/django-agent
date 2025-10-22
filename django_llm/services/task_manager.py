from django.core.management import call_command
from django.db.migrations.executor import MigrationExecutor
from django.db import connections, transaction
from ..models import LLMRun, Task
from .codemods import Codemods
import os
import difflib
import shutil

class RollbackManager:
    def __init__(self):
        self.backups = {}
        self.created_dirs = []
        self.migrations = []

    def backup_file(self, path):
        if os.path.exists(path):
            self.backups[path] = Codemods.get_original_code(path)

    def add_created_dir(self, path):
        self.created_dirs.append(path)

    def add_migration(self, app_label, migration_name):
        self.migrations.append((app_label, migration_name))

    def rollback(self):
        for path, content in self.backups.items():
            with open(path, "w") as f:
                f.write(content)
        for path in self.created_dirs:
            if os.path.exists(path):
                shutil.rmtree(path)
        for app_label, migration_name in self.migrations:
            call_command('migrate', app_label, 'zero')

class TaskManager:
    @staticmethod
    def apply_run(run: LLMRun, dry_run=False):
        if not TaskManager.has_meaningful_test_suite():
            print("Warning: No meaningful test suite found. The AI's changes will be applied without verification.")

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
        elif op.get("op") == 'run_migrations':
            app_label = op.get('app')
            if rollback_manager:
                connection = connections['default']
                executor = MigrationExecutor(connection)
                targets = executor.loader.graph.leaf_nodes(app_label)
                if targets:
                    rollback_manager.add_migration(app_label, targets[0][1])

            call_command('makemigrations', app_label)
            call_command('migrate', app_label)

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
    def has_meaningful_test_suite(base_dir=".") -> bool:
        from django.apps import apps
        for app_config in apps.get_app_configs():
            # Ignore third-party apps
            if 'site-packages' in app_config.path:
                continue

            tests_py = os.path.join(app_config.path, "tests.py")
            tests_dir = os.path.join(app_config.path, "tests")

            if os.path.exists(tests_py):
                with open(tests_py, "r") as f:
                    content = f.read()
                    if "TestCase" in content:
                        return True

            if os.path.exists(tests_dir):
                for f in os.listdir(tests_dir):
                    if f.startswith("test_") and f.endswith(".py"):
                        return True
        return False

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

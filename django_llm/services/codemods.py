import libcst as cst
import os
from django.conf import settings
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand

class AddModelCommand(VisitorBasedCodemodCommand):
    def __init__(self, context: CodemodContext, model_name: str, fields: dict[str, str]):
        super().__init__(context)
        self.model_name = model_name
        self.fields = fields

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        model_class = cst.ClassDef(
            name=cst.Name(self.model_name),
            bases=[cst.Arg(value=cst.parse_expression("models.Model"))],
            body=cst.IndentedBlock(
                body=[
                    cst.SimpleStatementLine(
                        body=[
                            cst.Assign(
                                targets=[cst.AssignTarget(target=cst.Name(field_name))],
                                value=cst.parse_expression(field_type),
                            )
                        ]
                    )
                    for field_name, field_type in self.fields.items()
                ]
            ),
        )
        return updated_node.with_changes(body=[*updated_node.body, model_class])

class AddModelFormCommand(VisitorBasedCodemodCommand):
    def __init__(self, context: CodemodContext, model_name: str):
        super().__init__(context)
        self.model_name = model_name

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        form_class = cst.ClassDef(
            name=cst.Name(f"{self.model_name}Form"),
            bases=[cst.Arg(value=cst.parse_expression("forms.ModelForm"))],
            body=cst.IndentedBlock(
                body=[
                    cst.ClassDef(
                        name=cst.Name("Meta"),
                        bases=[],
                        body=cst.IndentedBlock(
                            body=[
                                cst.SimpleStatementLine(
                                    body=[
                                        cst.Assign(
                                            targets=[cst.AssignTarget(target=cst.Name("model"))],
                                            value=cst.Name(self.model_name),
                                        )
                                    ]
                                ),
                                cst.SimpleStatementLine(
                                    body=[
                                        cst.Assign(
                                            targets=[cst.AssignTarget(target=cst.Name("fields"))],
                                            value=cst.SimpleString("'__all__'"),
                                        )
                                    ]
                                )
                            ]
                        )
                    )
                ]
            )
        )
        return updated_node.with_changes(body=[*updated_node.body, form_class])

class RegisterModelAdminCommand(VisitorBasedCodemodCommand):
    def __init__(self, context: CodemodContext, model_name: str):
        super().__init__(context)
        self.model_name = model_name

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        import_statement = cst.parse_statement("from . import models")
        register_statement = cst.parse_statement(f"admin.site.register(models.{self.model_name})")

        return updated_node.with_changes(body=[import_statement, *updated_node.body, register_statement])


class AddViewCommand(VisitorBasedCodemodCommand):
    def __init__(self, context: CodemodContext, view_name: str, view_type: str, model: str, form_class: str = None, success_url: str = None):
        super().__init__(context)
        self.view_name = view_name
        self.view_type = view_type
        self.model = model
        self.form_class = form_class
        self.success_url = success_url

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        body = [
            cst.SimpleStatementLine(
                body=[
                    cst.Assign(
                        targets=[cst.AssignTarget(target=cst.Name("model"))],
                        value=cst.Name(self.model),
                    )
                ]
            )
        ]
        if self.form_class:
            body.append(
                cst.SimpleStatementLine(
                    body=[
                        cst.Assign(
                            targets=[cst.AssignTarget(target=cst.Name("form_class"))],
                            value=cst.Name(self.form_class),
                        )
                    ]
                )
            )
        if self.success_url:
            body.append(
                cst.SimpleStatementLine(
                    body=[
                        cst.Assign(
                            targets=[cst.AssignTarget(target=cst.Name("success_url"))],
                            value=cst.SimpleString(f"'{self.success_url}'"),
                        )
                    ]
                )
            )

        view_class = cst.ClassDef(
            name=cst.Name(self.view_name),
            bases=[cst.Arg(value=cst.parse_expression(f"generic.{self.view_type}"))],
            body=cst.IndentedBlock(body=body),
        )
        return updated_node.with_changes(body=[*updated_node.body, view_class])

class AddUrlCommand(VisitorBasedCodemodCommand):
    def __init__(self, context: CodemodContext, url_pattern: str):
        super().__init__(context)
        self.url_pattern = url_pattern

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        if original_node.targets[0].target.value == "urlpatterns":
            new_element = cst.Element(value=cst.parse_expression(self.url_pattern))
            updated_list = updated_node.value.with_changes(elements=[*updated_node.value.elements, new_element])
            return updated_node.with_changes(value=updated_list)
        return updated_node

class IncludeUrlConfCommand(VisitorBasedCodemodCommand):
    def __init__(self, context: CodemodContext, app_name: str):
        super().__init__(context)
        self.app_name = app_name

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        if original_node.targets[0].target.value == "urlpatterns":
            new_element = cst.Element(value=cst.parse_expression(f"path('{self.app_name}/', include('{self.app_name}.urls'))"))
            updated_list = updated_node.value.with_changes(elements=[*updated_node.value.elements, new_element])
            return updated_node.with_changes(value=updated_list)
        return updated_node

class Codemods:
    @staticmethod
    def get_original_code(path: str) -> str:
        with open(path, "r") as f:
            return f.read()

    @staticmethod
    def _get_models_path(app_name: str, base_dir=".") -> str:
        return os.path.join(base_dir, app_name, "models.py")

    @staticmethod
    def _get_admin_path(app_name: str, base_dir=".") -> str:
        return os.path.join(base_dir, app_name, "admin.py")

    @staticmethod
    def _get_forms_path(app_name: str, base_dir=".") -> str:
        return os.path.join(base_dir, app_name, "forms.py")

    @staticmethod
    def _get_views_path(app_name: str, base_dir=".") -> str:
        return os.path.join(base_dir, app_name, "views.py")

    @staticmethod
    def _get_template_path(template_name: str, base_dir=".") -> str:
        return os.path.join(base_dir, "templates", template_name)

    @staticmethod
    def _get_urls_path(app_name: str, base_dir=".") -> str:
        return os.path.join(base_dir, app_name, "urls.py")

    @staticmethod
    def _get_project_urls_path(base_dir=".") -> str:
        if getattr(settings, 'TESTING', False):
            return os.path.join(base_dir, "django_llm", "test_urls.py")
        urlconf_module = settings.ROOT_URLCONF
        return os.path.join(base_dir, urlconf_module.replace(".", "/")) + ".py"

    @staticmethod
    def add_model(app_name: str, model_name: str, fields: dict[str, str], dry_run=False, base_dir="."):
        models_path = Codemods._get_models_path(app_name, base_dir=base_dir)
        source = Codemods.get_original_code(models_path)

        context = CodemodContext()
        command = AddModelCommand(context, model_name, fields)
        tree = cst.parse_module(source)
        modified_tree = command.transform_module(tree)

        if dry_run:
            return modified_tree.code

        with open(models_path, "w") as f:
            f.write(modified_tree.code)

    @staticmethod
    def add_form(app_name: str, model_name: str, dry_run=False, base_dir="."):
        forms_path = Codemods._get_forms_path(app_name, base_dir=base_dir)
        if not os.path.exists(forms_path):
            with open(forms_path, "w") as f:
                f.write("from django import forms\nfrom .models import *\n")

        source = Codemods.get_original_code(forms_path)

        context = CodemodContext()
        command = AddModelFormCommand(context, model_name)
        tree = cst.parse_module(source)
        modified_tree = command.transform_module(tree)

        if dry_run:
            return modified_tree.code

        with open(forms_path, "w") as f:
            f.write(modified_tree.code)

    @staticmethod
    def register_model_admin(app_name: str, model_name: str, dry_run=False, base_dir="."):
        admin_path = Codemods._get_admin_path(app_name, base_dir=base_dir)
        source = Codemods.get_original_code(admin_path)

        context = CodemodContext()
        command = RegisterModelAdminCommand(context, model_name)
        tree = cst.parse_module(source)
        modified_tree = command.transform_module(tree)

        if dry_run:
            return modified_tree.code

        with open(admin_path, "w") as f:
            f.write(modified_tree.code)

    @staticmethod
    def add_view(app_name: str, view_name: str, view_type: str, model: str, form_class: str = None, success_url: str = None, dry_run=False, base_dir="."):
        views_path = Codemods._get_views_path(app_name, base_dir=base_dir)
        source = Codemods.get_original_code(views_path)

        context = CodemodContext()
        command = AddViewCommand(context, view_name, view_type, model, form_class, success_url)
        tree = cst.parse_module(source)
        modified_tree = command.transform_module(tree)

        if dry_run:
            return modified_tree.code

        with open(views_path, "w") as f:
            f.write(modified_tree.code)

    @staticmethod
    def add_template(template_name: str, content: str, dry_run=False, base_dir="."):
        if dry_run:
            return content
        template_path = Codemods._get_template_path(template_name, base_dir=base_dir)
        os.makedirs(os.path.dirname(template_path), exist_ok=True)
        with open(template_path, "w") as f:
            f.write(content)

    @staticmethod
    def add_url(app_name: str, url_pattern: str, dry_run=False, base_dir="."):
        urls_path = Codemods._get_urls_path(app_name, base_dir=base_dir)
        if not os.path.exists(urls_path):
            with open(urls_path, "w") as f:
                f.write("from django.urls import path\nfrom . import views\n\nurlpatterns = []\n")

        source = Codemods.get_original_code(urls_path)

        context = CodemodContext()
        command = AddUrlCommand(context, url_pattern)
        tree = cst.parse_module(source)
        modified_tree = command.transform_module(tree)

        if dry_run:
            return modified_tree.code

        with open(urls_path, "w") as f:
            f.write(modified_tree.code)

    @staticmethod
    def include_url_conf(app_name: str, dry_run=False, base_dir="."):
        project_urls_path = Codemods._get_project_urls_path(base_dir=base_dir)
        source = Codemods.get_original_code(project_urls_path)

        context = CodemodContext()
        command = IncludeUrlConfCommand(context, app_name)
        tree = cst.parse_module(source)
        modified_tree = command.transform_module(tree)

        if dry_run:
            return modified_tree.code

        with open(project_urls_path, "w") as f:
            f.write(modified_tree.code)

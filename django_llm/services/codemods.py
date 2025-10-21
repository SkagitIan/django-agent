import libcst as cst
import os
from django.conf import settings
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand

class AddModelCommand(VisitorBasedCodemodCommand):
    def __init__(self, context: CodemodContext, model_name: str, fields: list[str]):
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
                                targets=[cst.AssignTarget(target=cst.Name(field))],
                                value=cst.parse_expression("models.CharField(max_length=100)"),
                            )
                        ]
                    )
                    for field in self.fields
                ]
            ),
        )
        return updated_node.with_changes(body=[*updated_node.body, model_class])

class AddViewCommand(VisitorBasedCodemodCommand):
    def __init__(self, context: CodemodContext, view_name: str):
        super().__init__(context)
        self.view_name = view_name

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        view_func = cst.FunctionDef(
            name=cst.Name(self.view_name),
            params=cst.Parameters(params=[cst.Param(name=cst.Name("request"))]),
            body=cst.IndentedBlock(
                body=[
                    cst.SimpleStatementLine(
                        body=[
                            cst.Return(
                                value=cst.parse_expression("HttpResponse('Hello, world!')")
                            )
                        ]
                    )
                ]
            ),
        )
        return updated_node.with_changes(body=[*updated_node.body, view_func])

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
    def _get_models_path(app_name: str) -> str:
        return f"{app_name}/models.py"

    @staticmethod
    def _get_views_path(app_name: str) -> str:
        return f"{app_name}/views.py"

    @staticmethod
    def _get_template_path(template_name: str) -> str:
        return f"templates/{template_name}"

    @staticmethod
    def _get_urls_path(app_name: str) -> str:
        return f"{app_name}/urls.py"

    @staticmethod
    def _get_project_urls_path() -> str:
        if getattr(settings, 'TESTING', False):
            return "django_llm/test_urls.py"
        urlconf_module = settings.ROOT_URLCONF
        return urlconf_module.replace(".", "/") + ".py"

    @staticmethod
    def add_model(app_name: str, model_name: str, fields: list[str]):
        models_path = Codemods._get_models_path(app_name)
        with open(models_path, "r") as f:
            source = f.read()

        context = CodemodContext()
        command = AddModelCommand(context, model_name, fields)
        tree = cst.parse_module(source)
        modified_tree = command.transform_module(tree)

        with open(models_path, "w") as f:
            f.write(modified_tree.code)

    @staticmethod
    def add_view(app_name: str, view_name: str):
        views_path = Codemods._get_views_path(app_name)
        with open(views_path, "r") as f:
            source = f.read()

        context = CodemodContext()
        command = AddViewCommand(context, view_name)
        tree = cst.parse_module(source)
        modified_tree = command.transform_module(tree)

        with open(views_path, "w") as f:
            f.write(modified_tree.code)

    @staticmethod
    def add_template(template_name: str, content: str):
        template_path = Codemods._get_template_path(template_name)
        os.makedirs(os.path.dirname(template_path), exist_ok=True)
        with open(template_path, "w") as f:
            f.write(content)

    @staticmethod
    def add_url(app_name: str, url_pattern: str):
        urls_path = Codemods._get_urls_path(app_name)
        with open(urls_path, "r") as f:
            source = f.read()

        context = CodemodContext()
        command = AddUrlCommand(context, url_pattern)
        tree = cst.parse_module(source)
        modified_tree = command.transform_module(tree)

        with open(urls_path, "w") as f:
            f.write(modified_tree.code)

    @staticmethod
    def include_url_conf(app_name: str):
        project_urls_path = Codemods._get_project_urls_path()
        with open(project_urls_path, "r") as f:
            source = f.read()

        context = CodemodContext()
        command = IncludeUrlConfCommand(context, app_name)
        tree = cst.parse_module(source)
        modified_tree = command.transform_module(tree)

        with open(project_urls_path, "w") as f:
            f.write(modified_tree.code)

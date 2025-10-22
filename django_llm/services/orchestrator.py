import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from ..models import LLMRun

load_dotenv()

class Orchestrator:
    @staticmethod
    def _get_plan_schema():
        return {
            "type": "object",
            "properties": {
                "operations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {"type": "string"},
                            "app": {"type": "string"},
                            "model": {"type": "string"},
                            "fields": {
                                "type": "object",
                                "patternProperties": {
                                    "^[a-zA-Z_][a-zA-Z0-9_]*$": {"type": "string"}
                                }
                            },
                            "name": {"type": "string"},
                            "content": {"type": "string"},
                            "pattern": {"type": "string"},
                            "view_type": {"type": "string"},
                            "template_name": {"type": "string"},
                        },
                        "required": ["op"],
                    },
                }
            },
            "required": ["operations"],
        }

    @staticmethod
    def create_run(prompt: str, user) -> LLMRun:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        system_prompt = """
        You are a Django code architect.
        Analyze the following prompt and generate a plan of safe operations to build a complete CRUD interface.
        Return JSON with a list of operations only.

        Allowed ops: create_app, add_model, add_form, add_view, add_template, add_url, run_migrations.

        - For `add_model`, `fields` should be a dictionary mapping field names to their Django model field types (e.g., "name": "models.CharField(max_length=100)").
        - After an `add_model` operation, you must add a `run_migrations` operation for the same app.
        - For `add_form`, you must specify the `app` and `model`.
        - For `add_view`, you must specify the `app`, `name` (the view's class name), and `view_type` (e.g., "ListView", "DetailView", "CreateView", "UpdateView", "DeleteView").
        - For `add_template`, you must specify the `name` (e.g., "my_app/my_model_list.html") and the full HTML `content`.
        - For `add_url`, you must specify the `app` and the `pattern` (e.g., "path('', views.MyModelListView.as_view(), name='mymodel_list')").

        Example for "add a blog app with posts that have a title and content":
        {
            "operations": [
                {"op": "create_app", "name": "blog"},
                {"op": "add_model", "app": "blog", "model": "Post", "fields": {"title": "models.CharField(max_length=200)", "content": "models.TextField()"}},
                {"op": "run_migrations", "app": "blog"},
                {"op": "add_form", "app": "blog", "model": "Post"},
                {"op": "add_view", "app": "blog", "name": "PostListView", "view_type": "ListView", "model": "Post"},
                {"op": "add_view", "app": "blog", "name": "PostDetailView", "view_type": "DetailView", "model": "Post"},
                {"op": "add_view", "app": "blog", "name": "PostCreateView", "view_type": "CreateView", "model": "Post", "form_class": "PostForm"},
                {"op": "add_view", "app": "blog", "name": "PostUpdateView", "view_type": "UpdateView", "model": "Post", "form_class": "PostForm"},
                {"op": "add_view", "app": "blog", "name": "PostDeleteView", "view_type": "DeleteView", "model": "Post", "success_url": "/blog/"},
                {"op": "add_template", "name": "blog/post_list.html", "content": "<!DOCTYPE html>..."},
                {"op": "add_template", "name": "blog/post_detail.html", "content": "<!DOCTYPE html>..."},
                {"op": "add_template", "name": "blog/post_form.html", "content": "<!DOCTYPE html>..."},
                {"op": "add_template", "name": "blog/post_confirm_delete.html", "content": "<!DOCTYPE html>..."},
                {"op": "add_url", "app": "blog", "pattern": "path('', views.PostListView.as_view(), name='post_list')"},
                {"op": "add_url", "app": "blog", "pattern": "path('<int:pk>/', views.PostDetailView.as_view(), name='post_detail')"},
                {"op": "add_url", "app": "blog", "pattern": "path('new/', views.PostCreateView.as_view(), name='post_create')"},
                {"op": "add_url", "app": "blog", "pattern": "path('<int:pk>/edit/', views.PostUpdateView.as_view(), name='post_update')"},
                {"op": "add_url", "app": "blog", "pattern": "path('<int:pk>/delete/', views.PostDeleteView.as_view(), name='post_delete')"}
            ]
        }
        """

        full_prompt = f"{system_prompt}\n\nUser prompt: {prompt}"

        response = client.responses.create(
            model="gpt-4",
            input=full_prompt,
            text={"format": Orchestrator._get_plan_schema()},
        )

        plan_str = response.output[0].content[0].text
        plan = json.loads(plan_str)

        run = LLMRun.objects.create(prompt=prompt, plan=plan, requester=user, run_type='USER')
        return run

    @staticmethod
    def get_fix(stacktrace: str) -> dict:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        with open("django_llm/prompts/skills/fixer.txt", "r") as f:
            prompt_template = f.read()

        prompt = prompt_template.format(stacktrace=stacktrace)
        response = client.responses.create(
            model="gpt-4",
            input=prompt,
            text={"format": Orchestrator._get_plan_schema()},
        )
        plan_str = response.output[0].content[0].text
        return json.loads(plan_str)

    @staticmethod
    def get_explanation(logs: str) -> str:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        with open("django_llm/prompts/skills/explainer.txt", "r") as f:
            prompt_template = f.read()

        prompt = prompt_template.format(logs=logs)
        response = client.responses.create(
            model="gpt-4",
            input=prompt,
        )
        return response.output[0].content[0].text

    @staticmethod
    def get_security_audit(report: str) -> str:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        with open("django_llm/prompts/skills/security_auditor.txt", "r") as f:
            prompt_template = f.read()

        prompt = prompt_template.format(report=report)
        response = client.responses.create(
            model="gpt-4",
            input=prompt,
        )
        return response.output[0].content[0].text

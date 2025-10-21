import json
import os
import shutil
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.conf import settings
from django.contrib.auth.models import User
from .models import LLMRun, Task
from .services.orchestrator import Orchestrator
from .services.task_manager import TaskManager
from .services.codemods import Codemods

class CodemodTestCase(TestCase):
    def setUp(self):
        self.app_name = "test_app"
        os.makedirs(self.app_name, exist_ok=True)
        with open(f"{self.app_name}/models.py", "w") as f:
            f.write("from django.db import models\n")
        with open(f"{self.app_name}/views.py", "w") as f:
            f.write("from django.http import HttpResponse\n")
        with open(f"{self.app_name}/urls.py", "w") as f:
            f.write("from django.urls import path\nurlpatterns = []\n")
        os.makedirs("templates", exist_ok=True)


    def tearDown(self):
        if os.path.exists(self.app_name):
            shutil.rmtree(self.app_name)
        if os.path.exists("templates"):
            shutil.rmtree("templates")

    def test_add_model(self):
        Codemods.add_model(self.app_name, "TestModel", ["field1", "field2"])
        with open(f"{self.app_name}/models.py", "r") as f:
            content = f.read()
        self.assertIn("class TestModel(models.Model):", content)
        self.assertIn("field1 = models.CharField(max_length=100)", content)

    def test_add_view(self):
        Codemods.add_view(self.app_name, "test_view")
        with open(f"{self.app_name}/views.py", "r") as f:
            content = f.read()
        self.assertIn("def test_view(request):", content)

    def test_add_template(self):
        Codemods.add_template("test_template.html", "<h1>Hello</h1>")
        with open("templates/test_template.html", "r") as f:
            content = f.read()
        self.assertEqual(content, "<h1>Hello</h1>")

    def test_add_url(self):
        Codemods.add_url(self.app_name, "path('test/', views.test_view, name='test_view')")
        with open(f"{self.app_name}/urls.py", "r") as f:
            content = f.read()
        self.assertIn("path('test/', views.test_view, name='test_view')", content)


class OrchestratorTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')

    @patch('openai.resources.responses.Responses.create')
    def test_create_run(self, mock_create):
        mock_response = MagicMock()
        mock_response.output = [MagicMock()]
        mock_response.output[0].content = [MagicMock()]
        mock_response.output[0].content[0].text = json.dumps({
            "operations": [
                {"op": "create_app", "name": "contact"},
            ]
        })
        mock_create.return_value = mock_response

        run = Orchestrator.create_run(prompt='test prompt', user=self.user)
        self.assertIsInstance(run, LLMRun)
        self.assertEqual(run.prompt, 'test prompt')
        self.assertEqual(run.requester, self.user)
        self.assertEqual(run.plan['operations'][0]['op'], 'create_app')

class TaskManagerTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.app_name = "test_contact_app"
        self.run = LLMRun.objects.create(
            prompt='test prompt',
            plan={
                "operations": [
                    {"op": "create_app", "name": self.app_name},
                    {"op": "add_model", "app": self.app_name, "model": "Contact", "fields": ["name", "email"]},
                    {"op": "add_view", "app": self.app_name, "name": "contact_view"},
                    {"op": "add_template", "name": f"{self.app_name}/contact.html", "content": "<h1>Contact Us</h1>"},
                    {"op": "add_url", "app": self.app_name, "pattern": "path('contact/', views.contact_view, name='contact_view')"}
                ]
            },
            requester=self.user
        )
        with open("django_llm/test_urls.py", "r") as f:
            self.original_urls_content = f.read()


    def tearDown(self):
        if os.path.exists(self.app_name):
            shutil.rmtree(self.app_name)
        if os.path.exists("templates"):
            shutil.rmtree("templates")
        with open("django_llm/test_urls.py", "w") as f:
            f.write(self.original_urls_content)


    def test_apply_run(self):
        TaskManager.apply_run(self.run)
        self.assertEqual(Task.objects.filter(run=self.run).count(), 5)
        for task in Task.objects.filter(run=self.run):
            self.assertEqual(task.status, 'APPLIED')

        # Verify that the app was created
        self.assertTrue(os.path.exists(self.app_name))

        # Verify that the model was added
        with open(f"{self.app_name}/models.py", "r") as f:
            content = f.read()
        self.assertIn("class Contact(models.Model):", content)

        # Verify that the view was added
        with open(f"{self.app_name}/views.py", "r") as f:
            content = f.read()
        self.assertIn("def contact_view(request):", content)

        # Verify that the template was created
        self.assertTrue(os.path.exists(f"templates/{self.app_name}/contact.html"))

        # Verify that the URL was added
        with open(f"{self.app_name}/urls.py", "r") as f:
            content = f.read()
        self.assertIn("path('contact/', views.contact_view, name='contact_view')", content)

import json
import os
import shutil
import logging
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.conf import settings
from django.contrib.auth.models import User
from django.core.signals import got_request_exception
from django.db.models.signals import post_save
from django.test.client import RequestFactory

from .models import LLMRun, Task, LLMLog
from .services.orchestrator import Orchestrator
from .services.task_manager import TaskManager, RollbackManager
from .services.codemods import Codemods
from .services.monitor_agent import collect_metrics, analyze_logs

class BaseTestCase(TestCase):
    def setUp(self):
        LLMLog.objects.all().delete()

    def tearDown(self):
        LLMLog.objects.all().delete()

class CodemodTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.app_name = "test_app"
        os.makedirs(self.app_name, exist_ok=True)
        with open(f"{self.app_name}/models.py", "w") as f:
            f.write("from django.db import models\n")
        with open(f"{self.app_name}/admin.py", "w") as f:
            f.write("from django.contrib import admin\n")
        with open(f"{self.app_name}/views.py", "w") as f:
            f.write("from django.http import HttpResponse\nfrom django.views import generic\n")
        with open(f"{self.app_name}/urls.py", "w") as f:
            f.write("from django.urls import path\nurlpatterns = []\n")
        os.makedirs("templates", exist_ok=True)


    def tearDown(self):
        super().tearDown()
        if os.path.exists(self.app_name):
            shutil.rmtree(self.app_name)
        if os.path.exists("templates"):
            shutil.rmtree("templates")

    def test_add_model(self):
        fields = {"name": "models.CharField(max_length=100)", "email": "models.EmailField()"}
        Codemods.add_model(self.app_name, "TestModel", fields)
        with open(f"{self.app_name}/models.py", "r") as f:
            content = f.read()
        self.assertIn("class TestModel(models.Model):", content)
        self.assertIn("name = models.CharField(max_length=100)", content)
        self.assertIn("email = models.EmailField()", content)

    def test_register_model_admin(self):
        Codemods.register_model_admin(self.app_name, "TestModel")
        with open(f"{self.app_name}/admin.py", "r") as f:
            content = f.read()
        self.assertIn("from . import models", content)
        self.assertIn("admin.site.register(models.TestModel)", content)

    def test_add_view(self):
        Codemods.add_view(self.app_name, "TestView", "ListView", "TestModel")
        with open(f"{self.app_name}/views.py", "r") as f:
            content = f.read()
        self.assertIn("class TestView(generic.ListView):", content)
        self.assertIn("model = TestModel", content)

    def test_add_template(self):
        Codemods.add_template("test_template.html", "<h1>Hello</h1>")
        with open("templates/test_template.html", "r") as f:
            content = f.read()
        self.assertEqual(content, "<h1>Hello</h1>")

    def test_add_url(self):
        Codemods.add_url(self.app_name, "path('test/', views.TestView.as_view(), name='test_view')")
        with open(f"{self.app_name}/urls.py", "r") as f:
            content = f.read()
        self.assertIn("path('test/', views.TestView.as_view(), name='test_view')", content)


class OrchestratorTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
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
        self.assertEqual(run.run_type, 'USER')
        self.assertEqual(run.plan['operations'][0]['op'], 'create_app')

class TaskManagerTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.app_name = "test_contact_app"
        self.run = LLMRun.objects.create(
            prompt='test prompt',
            plan={
                "operations": [
                    {"op": "create_app", "name": self.app_name},
                    {"op": "add_model", "app": self.app_name, "model": "Contact", "fields": {"name": "models.CharField(max_length=100)", "email": "models.EmailField()"}},
                    {"op": "add_form", "app": self.app_name, "model": "Contact"},
                    {"op": "add_view", "app": self.app_name, "name": "ContactListView", "view_type": "ListView", "model": "Contact"},
                    {"op": "add_template", "name": f"{self.app_name}/contact_list.html", "content": "<h1>Contact List</h1>"},
                    {"op": "add_url", "app": self.app_name, "pattern": "path('', views.ContactListView.as_view(), name='contact_list')"}
                ]
            },
            requester=self.user
        )
        with open("django_llm/test_urls.py", "r") as f:
            self.original_urls_content = f.read()


    def tearDown(self):
        super().tearDown()
        if os.path.exists(self.app_name):
            shutil.rmtree(self.app_name)
        if os.path.exists("templates"):
            shutil.rmtree("templates")
        with open("django_llm/test_urls.py", "w") as f:
            f.write(self.original_urls_content)


    def test_apply_run(self):
        TaskManager.apply_run(self.run)
        self.assertEqual(Task.objects.filter(run=self.run).count(), 6)
        for task in Task.objects.filter(run=self.run):
            self.assertEqual(task.status, 'APPLIED')

        self.assertTrue(os.path.exists(self.app_name))

        with open(f"{self.app_name}/models.py", "r") as f:
            content = f.read()
        self.assertIn("class Contact(models.Model):", content)

        with open(f"{self.app_name}/forms.py", "r") as f:
            content = f.read()
        self.assertIn("class ContactForm(forms.ModelForm):", content)

        with open(f"{self.app_name}/views.py", "r") as f:
            content = f.read()
        self.assertIn("class ContactListView(generic.ListView):", content)

        self.assertTrue(os.path.exists(f"templates/{self.app_name}/contact_list.html"))

        with open(f"{self.app_name}/urls.py", "r") as f:
            content = f.read()
        self.assertIn("path('', views.ContactListView.as_view(), name='contact_list')", content)

    def test_rollback(self):
        original_content = "original content"
        with open("test.txt", "w") as f:
            f.write(original_content)

        rollback_manager = RollbackManager()
        rollback_manager.backup_file("test.txt")

        with open("test.txt", "w") as f:
            f.write("new content")

        rollback_manager.rollback()

        with open("test.txt", "r") as f:
            content = f.read()
        self.assertEqual(content, original_content)
        os.remove("test.txt")


class MonitorTestCase(BaseTestCase):
    def test_llmlog_creation(self):
        log = LLMLog.objects.create(source='test', level='INFO', message='Test log')
        self.assertEqual(LLMLog.objects.count(), 1)
        self.assertEqual(log.message, 'Test log')

    def test_log_request_exception_signal(self):
        factory = RequestFactory()
        request = factory.get('/test')
        got_request_exception.send(sender=None, request=request)
        self.assertEqual(LLMLog.objects.filter(source='django.request', level='ERROR').count(), 1)

    def test_log_post_save_signal(self):
        user = User.objects.create_user(username='signaltest', password='password')
        log_count = LLMLog.objects.filter(source='django.db.models').count()
        user.save()
        self.assertGreater(LLMLog.objects.filter(source='django.db.models').count(), log_count)

    def test_logging_handler(self):
        logger = logging.getLogger('django')
        logger.info('This is a test log message.')
        self.assertTrue(LLMLog.objects.filter(source='django', level='INFO', message='This is a test log message.').exists())

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_collect_metrics_task(self, mock_disk_usage, mock_virtual_memory, mock_cpu_percent):
        mock_cpu_percent.return_value = 50.0
        mock_virtual_memory.return_value = MagicMock(percent=60.0)
        mock_disk_usage.return_value = MagicMock(percent=70.0)

        collect_metrics()

        log = LLMLog.objects.get(source='monitor_agent')
        self.assertEqual(log.level, 'INFO')
        self.assertEqual(log.message, 'System metrics')
        self.assertEqual(log.details['cpu_percent'], 50.0)
        self.assertEqual(log.details['memory_percent'], 60.0)
        self.assertEqual(log.details['disk_percent'], 70.0)

    @patch('django_llm.services.orchestrator.Orchestrator.get_fix')
    @patch('subprocess.run')
    def test_analyze_logs_task_sandbox(self, mock_subprocess_run, mock_get_fix):
        mock_get_fix.return_value = {
            "operations": [
                {"op": "fix_error", "name": "test_fix"},
            ]
        }
        # Simulate successful test run
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        LLMLog.objects.create(source='test', level='ERROR', message='Test error')
        analyze_logs()
        self.assertTrue(LLMRun.objects.filter(run_type='AI').exists())
        self.assertTrue(Task.objects.filter(op='fix_error').exists())

class UIViewTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='testuser', password='password', is_staff=True, is_superuser=True)
        self.client.login(username='testuser', password='password')
        self.run = LLMRun.objects.create(prompt="test", plan={}, requester=self.user)

    def test_review_run_view(self):
        response = self.client.get(f'/llm/tasks/review/{self.run.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review Run")
        self.assertContains(response, "prism.min.css")
        self.assertContains(response, "prism.min.js")

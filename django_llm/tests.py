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
from django.db.migrations.executor import MigrationExecutor
from django.db import connections

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

@override_settings(ROOT_URLCONF='myproject.urls')
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

@override_settings(ROOT_URLCONF='myproject.urls')
class TaskManagerTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.app_name = "test_app"

        plan = {
            "operations": [
                {"op": "add_model", "app": self.app_name, "model": "Contact", "fields": {"name": "models.CharField(max_length=100)", "email": "models.EmailField()"}},
                {"op": "run_migrations", "app": self.app_name},
            ]
        }
        self.run = LLMRun.objects.create(
            prompt='test prompt',
            plan=plan,
            requester=self.user
        )
        # Create a dummy app structure for the test
        os.makedirs(self.app_name, exist_ok=True)
        with open(f"{self.app_name}/models.py", "w") as f:
            f.write("from django.db import models\n")
        with open(f"{self.app_name}/admin.py", "w") as f:
            f.write("from django.contrib import admin\n")


    def tearDown(self):
        super().tearDown()
        if os.path.exists(self.app_name):
            shutil.rmtree(self.app_name)


    @patch('django_llm.services.task_manager.call_command')
    def test_apply_run(self, mock_call_command):
        TaskManager.apply_run(self.run)
        self.assertEqual(Task.objects.filter(run=self.run).count(), 2)
        for task in Task.objects.filter(run=self.run):
            self.assertEqual(task.status, 'APPLIED')

        with open(f"{self.app_name}/models.py", "r") as f:
            content = f.read()
        self.assertIn("class Contact(models.Model):", content)

        mock_call_command.assert_any_call('makemigrations', self.app_name)
        mock_call_command.assert_any_call('migrate', self.app_name)

    @patch('django_llm.services.task_manager.TaskManager.apply_op')
    @patch('django_llm.services.task_manager.RollbackManager.rollback')
    def test_migration_rollback(self, mock_rollback, mock_apply_op):
        mock_apply_op.side_effect = Exception("Test exception")

        with self.assertRaises(Exception):
            TaskManager.apply_run(self.run)

        mock_rollback.assert_called_once()


@override_settings(ROOT_URLCONF='myproject.urls')
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

@override_settings(ROOT_URLCONF='myproject.urls')
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

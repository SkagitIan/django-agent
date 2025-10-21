from django.core.management.base import BaseCommand
from ...models import LLMRun
from ...services.task_manager import TaskManager

class Command(BaseCommand):
    help = 'Applies a run.'

    def add_arguments(self, parser):
        parser.add_argument('run_id', type=int, help='The ID of the run to apply.')

    def handle(self, *args, **options):
        run_id = options['run_id']
        try:
            run = LLMRun.objects.get(id=run_id)
            TaskManager.apply_run(run)
            self.stdout.write(self.style.SUCCESS(f'Successfully applied run {run.id}.'))
        except LLMRun.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Run with ID {run_id} does not exist.'))

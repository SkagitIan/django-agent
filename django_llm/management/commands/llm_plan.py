from django.core.management.base import BaseCommand
from ...services.orchestrator import Orchestrator

class Command(BaseCommand):
    help = 'Creates a plan from a prompt.'

    def add_arguments(self, parser):
        parser.add_argument('prompt', type=str, help='The prompt to create a plan from.')

    def handle(self, *args, **options):
        prompt = options['prompt']
        run = Orchestrator.create_run(prompt=prompt, user=None)
        self.stdout.write(self.style.SUCCESS(f'Successfully created plan for run {run.id}:'))
        for op in run.plan.get("operations", []):
            self.stdout.write(f'  - {op.get("op")}: {op.get("name")}')

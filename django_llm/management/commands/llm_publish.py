from django.core.management.base import BaseCommand
from ...services.deploy_agent import DeployAgent

class Command(BaseCommand):
    help = 'Publishes the application.'

    def handle(self, *args, **options):
        DeployAgent.publish()
        self.stdout.write(self.style.SUCCESS('Successfully published the application.'))

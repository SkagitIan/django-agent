from django.core.signals import got_request_exception
from django.db.models.signals import post_save, post_migrate
from django.db.migrations.recorder import MigrationRecorder
from django.dispatch import receiver
from .models import LLMLog

@receiver(got_request_exception)
def log_request_exception(sender, **kwargs):
    LLMLog.objects.create(
        source='django.request',
        level='ERROR',
        message='Request exception',
        details={'request': str(kwargs.get('request'))}
    )

@receiver(post_save)
def log_post_save(sender, **kwargs):
    if sender in [MigrationRecorder.Migration, LLMLog]:
        return
    LLMLog.objects.create(
        source='django.db.models',
        level='INFO',
        message=f'Saved an instance of {sender.__name__}',
        details={'instance': str(kwargs.get('instance'))}
    )

@receiver(post_migrate)
def log_post_migrate(sender, **kwargs):
    LLMLog.objects.create(
        source='django.db.migrations',
        level='INFO',
        message='Migrations applied',
        details={'app_config': str(kwargs.get('app_config'))}
    )

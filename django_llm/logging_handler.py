import logging

class LLMLoggingHandler(logging.Handler):
    def emit(self, record):
        from .models import LLMLog
        LLMLog.objects.create(
            source=record.name,
            level=record.levelname,
            message=record.getMessage(),
            details={
                'pathname': record.pathname,
                'lineno': record.lineno,
                'funcName': record.funcName,
            }
        )

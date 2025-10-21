from django.shortcuts import render
from ..models import LLMLog

def monitor(request):
    logs = LLMLog.objects.all().order_by('-timestamp')[:50]
    return render(request, 'django_llm/monitor.html', {'logs': logs})

from django.shortcuts import render, get_object_or_404
from ..models import LLMRun
from ..services.task_manager import TaskManager

def task_list(request):
    runs = LLMRun.objects.all().order_by("-created_at")
    return render(request, "django_llm/tasks.html", {"runs": runs})

def apply_run(request, run_id):
    run = get_object_or_404(LLMRun, id=run_id)
    TaskManager.apply_run(run)
    return render(request, "django_llm/partials/run_status.html", {"run": run})

from django.shortcuts import render, get_object_or_404
from ..models import LLMRun
from ..services.task_manager import TaskManager

def task_list(request):
    user_runs = LLMRun.objects.filter(run_type='USER').order_by("-created_at")
    ai_runs = LLMRun.objects.filter(run_type='AI').order_by("-created_at")
    return render(request, "django_llm/tasks.html", {"user_runs": user_runs, "ai_runs": ai_runs})

def apply_run(request, run_id):
    run = get_object_or_404(LLMRun, id=run_id)
    TaskManager.apply_run(run)
    return render(request, "django_llm/partials/run_status.html", {"run": run})

def review_run(request, run_id):
    run = get_object_or_404(LLMRun, id=run_id)
    TaskManager.apply_run(run, dry_run=True)
    return render(request, "django_llm/review_run.html", {"run": run})

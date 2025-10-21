from django.shortcuts import render
from django.views.decorators.http import require_POST
from ..services.orchestrator import Orchestrator

@require_POST
def chat(request):
    prompt = request.POST.get("prompt")
    run = Orchestrator.create_run(prompt=prompt, user=request.user)
    return render(request, "django_llm/partials/chat_reply.html", {"plan": run.plan})

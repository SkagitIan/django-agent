from django.urls import path
from .views import chat, tasks

app_name = "django_llm"

urlpatterns = [
    path("chat/", chat.chat, name="chat"),
    path("tasks/", tasks.task_list, name="task_list"),
    path("tasks/apply/<int:run_id>/", tasks.apply_run, name="apply_run"),
]

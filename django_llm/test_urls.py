from django.urls import path, include

urlpatterns = [
    path("llm/", include("django_llm.urls", namespace="django_llm")),
]

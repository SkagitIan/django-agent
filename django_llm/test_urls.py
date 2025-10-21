from django.urls import path, include
from django.contrib import admin

urlpatterns = [
    path('admin/', admin.site.urls),
    path("llm/", include("django_llm.urls", namespace="django_llm")),
]

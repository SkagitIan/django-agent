from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from .models import LLMRun, Task, Artifact

class LLMRunAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('chat/', self.admin_site.admin_view(self.chat_view), name='django_llm_chat'),
        ]
        return custom_urls + urls

    def chat_view(self, request):
        return render(request, 'django_llm/chat.html')

admin.site.register(LLMRun, LLMRunAdmin)
admin.site.register(Task)
admin.site.register(Artifact)

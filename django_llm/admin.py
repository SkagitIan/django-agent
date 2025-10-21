from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.urls import reverse
from .models import LLMRun, Task, Artifact, LLMLog

class LLMRunAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('chat/', self.admin_site.admin_view(self.chat_view), name='django_llm_chat'),
            path('monitor/', self.admin_site.admin_view(self.monitor_view), name='django_llm_monitor'),
        ]
        return custom_urls + urls

    def chat_view(self, request):
        return render(request, 'django_llm/chat.html')

    def monitor_view(self, request):
        return redirect(reverse('django_llm:monitor'))

admin.site.register(LLMRun, LLMRunAdmin)
admin.site.register(Task)
admin.site.register(Artifact)
admin.site.register(LLMLog)

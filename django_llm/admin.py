from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.urls import reverse
from .models import LLMRun, Task, Artifact, LLMLog

class LLMRunAdmin(admin.ModelAdmin):
    change_list_template = 'admin/django_llm/llmrun/change_list.html'

    class Media:
        css = {
            'all': ('django_llm/css/chat.css',)
        }

admin.site.register(LLMRun, LLMRunAdmin)
admin.site.register(Task)
admin.site.register(Artifact)
admin.site.register(LLMLog)

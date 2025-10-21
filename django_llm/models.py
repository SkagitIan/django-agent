from django.db import models
from django.contrib.auth.models import User

class LLMRun(models.Model):
    id = models.AutoField(primary_key=True)
    prompt = models.TextField()
    plan = models.JSONField()
    state = models.CharField(max_length=20, default='CREATED')
    created_at = models.DateTimeField(auto_now_add=True)
    requester = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    preview_url = models.URLField(blank=True, null=True)
    pr_url = models.URLField(blank=True, null=True)

class Task(models.Model):
    id = models.AutoField(primary_key=True)
    run = models.ForeignKey(LLMRun, on_delete=models.CASCADE)
    op = models.CharField(max_length=100)
    params = models.JSONField()
    diff = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default='PENDING')

class Artifact(models.Model):
    id = models.AutoField(primary_key=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    file_path = models.CharField(max_length=255)
    hash = models.CharField(max_length=64)
    diff_text = models.TextField()

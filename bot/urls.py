from django.urls import path

from . import views

urlpatterns = [
    path("webhook/", views.webhook, name="webhook"),
    path("health/", views.health, name="health"),
]

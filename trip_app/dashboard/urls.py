from django.urls import path

from .views import pilotage

urlpatterns = [
    path("pilotage/", pilotage.pilotage_dashboard, name="pilotage_dashboard"),
]

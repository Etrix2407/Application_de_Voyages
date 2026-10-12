from django.urls import path

from .views import export, pilotage

urlpatterns = [
    path("pilotage/", pilotage.pilotage_dashboard, name="pilotage_dashboard"),
    path("export/", export.export_orders, name="export_orders"),
    path("export/journal/", export.export_log, name="export_log"),
]

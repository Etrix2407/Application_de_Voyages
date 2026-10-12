from django.urls import path

from .views import export, operational, pilotage

urlpatterns = [
    path("", operational.operational_dashboard, name="operational_dashboard"),
    path("pilotage/", pilotage.pilotage_dashboard, name="pilotage_dashboard"),
    path("export/", export.export_orders, name="export_orders"),
    path("export/journal/", export.export_log, name="export_log"),
]

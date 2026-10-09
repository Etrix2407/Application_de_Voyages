from django.urls import path

from . import views

urlpatterns = [
    path("nouvelle/<int:destination_pk>/", views.create_order, name="create_order"),
]

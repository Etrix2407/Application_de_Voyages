from django.urls import path

from . import views

urlpatterns = [
    path("", views.my_orders, name="my_orders"),
    path("nouvelle/<int:destination_pk>/", views.create_order, name="create_order"),
    path("<int:pk>/", views.my_order_detail, name="my_order_detail"),
    path("<int:pk>/annuler/", views.cancel_my_order, name="cancel_my_order"),
]

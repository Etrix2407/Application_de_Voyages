from django.urls import path

from .views import client, manage

urlpatterns = [
    path("", client.my_orders, name="my_orders"),
    path("nouvelle/<int:destination_pk>/", client.create_order, name="create_order"),
    path("<int:pk>/", client.my_order_detail, name="my_order_detail"),
    path("<int:pk>/annuler/", client.cancel_my_order, name="cancel_my_order"),
    path("gestion/", manage.order_list, name="manage_orders"),
    path("gestion/<int:pk>/", manage.order_detail, name="manage_order_detail"),
    path("gestion/<int:pk>/confirmer/", manage.confirm_order, name="manage_confirm_order"),
    path("gestion/<int:pk>/annuler/", manage.cancel_order, name="manage_cancel_order"),
]

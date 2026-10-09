from django.urls import path

from promotions.views import manage

urlpatterns = [
    path("gestion/", manage.promotion_list, name="manage_promotions"),
    path("gestion/creer/", manage.create, name="manage_create_promotion"),
    path("gestion/<int:pk>/", manage.promotion_detail, name="manage_promotion_detail"),
    path("gestion/<int:pk>/modifier/", manage.edit, name="manage_edit_promotion"),
    path("gestion/<int:pk>/desactiver/", manage.disable, name="manage_disable_promotion"),
    path("gestion/<int:pk>/supprimer/", manage.delete, name="manage_delete_promotion"),
]

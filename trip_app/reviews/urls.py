from django.urls import path

from reviews.views import client, manage

urlpatterns = [
    path("", client.my_reviews, name="my_reviews"),
    path("voyage/<int:order_pk>/donner/", client.create_review, name="create_review"),
    path("<int:pk>/modifier/", client.edit_review, name="edit_review"),
    path("<int:pk>/supprimer/", client.remove_review, name="remove_review"),
    path("gestion/a-moderer/", manage.pending_list, name="manage_pending_reviews"),
    path("gestion/<int:pk>/", manage.review_detail, name="manage_review_detail"),
    path("gestion/<int:pk>/publier/", manage.publish_review, name="manage_publish_review"),
    path("gestion/<int:pk>/refuser/", manage.refuse_review, name="manage_refuse_review"),
]

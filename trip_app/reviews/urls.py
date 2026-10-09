from django.urls import path

from reviews import views

urlpatterns = [
    path("", views.my_reviews, name="my_reviews"),
    path("voyage/<int:order_pk>/donner/", views.create_review, name="create_review"),
    path("<int:pk>/modifier/", views.edit_review, name="edit_review"),
    path("<int:pk>/supprimer/", views.remove_review, name="remove_review"),
]

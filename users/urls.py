from django.urls import path

from . import views

app_name = "users"
urlpatterns = [
    path("list/", views.participants, name="list"),
    path("register/", views.register, name="register"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("edit-profile/", views.edit_profile, name="edit_profile"),
    path("change-password/", views.change_password, name="change_password"),
    path("<int:pk>/", views.detail, name="detail"),
]

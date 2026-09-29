from django.urls import path

from . import views

app_name = "projects"
urlpatterns = [
    path("list/", views.project_list, name="list"),
    path("skills/", views.skills, name="skills"),
    path("create-project/", views.create, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/complete/", views.complete, name="complete"),
    path("<int:pk>/toggle-participate/", views.toggle_participate, name="participate"),
    path("<int:pk>/skills/add/", views.add_skill, name="add_skill"),
    path("<int:pk>/skills/add", views.add_skill),
    path("<int:pk>/skills/<int:skill_id>/remove/", views.remove_skill, name="remove_skill"),
]

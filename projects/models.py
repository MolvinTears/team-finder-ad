from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse

from users.validators import validate_github


class Skill(models.Model):
    name = models.CharField("Название", max_length=124, unique=True)

    class Meta:
        ordering = [Lower("name"), "id"]
        verbose_name = "навык"
        verbose_name_plural = "навыки"
        constraints = [models.UniqueConstraint(Lower("name"), name="skill_name_case_unique")]

    def __str__(self):
        return self.name


class Project(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    name = models.CharField("Название", max_length=200)
    description = models.TextField("Описание", blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_projects",
        verbose_name="Автор",
    )
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    github_url = models.URLField("GitHub", blank=True, validators=[validate_github])
    status = models.CharField("Статус", max_length=6, choices=Status.choices, default=Status.OPEN)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="participated_projects",
        blank=True,
        verbose_name="Участники",
    )
    skills = models.ManyToManyField(
        Skill, related_name="projects", blank=True, verbose_name="Навыки"
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "проект"
        verbose_name_plural = "проекты"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["open", "closed"]), name="project_valid_status"
            )
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("projects:detail", args=[self.pk])

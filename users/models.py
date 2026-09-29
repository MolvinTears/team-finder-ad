from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone

from .avatars import avatar_file
from .validators import normalize_phone, validate_github


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Укажите email.")
        user = self.model(email=email.strip().lower(), **extra_fields)
        user.set_password(password)
        user.full_clean(exclude=["avatar"])
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not all(extra_fields.get(field) for field in ("is_staff", "is_superuser", "is_active")):
            raise ValueError("Администратор должен быть активным и иметь права staff/superuser.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("Имейл", unique=True)
    name = models.CharField("Имя", max_length=124)
    surname = models.CharField("Фамилия", max_length=124)
    avatar = models.ImageField("Аватар", upload_to="avatars/")
    phone = models.CharField("Телефон", max_length=12, unique=True, null=True, blank=True)
    github_url = models.URLField("GitHub", blank=True, validators=[validate_github])
    about = models.TextField("О себе", max_length=256, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    is_staff = models.BooleanField("Доступ к админке", default=False)
    date_joined = models.DateTimeField("Дата регистрации", default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "surname"]

    class Meta:
        ordering = ["-id"]
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        constraints = [models.UniqueConstraint(Lower("email"), name="users_email_case_unique")]

    def clean(self):
        super().clean()
        self.email = self.email.strip().lower()
        self.phone = normalize_phone(self.phone)

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        self.phone = normalize_phone(self.phone)
        if not self.avatar:
            picture = avatar_file(self.name)
            self.avatar.save(picture.name, picture, save=False)
        super().save(*args, **kwargs)

    def get_full_name(self):
        return f"{self.name} {self.surname}"

    def get_short_name(self):
        return self.name

    def get_absolute_url(self):
        return reverse("users:detail", args=[self.pk])

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

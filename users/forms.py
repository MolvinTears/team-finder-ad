from io import BytesIO
from uuid import uuid4

from django import forms
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .models import User
from .validators import normalize_phone


class EmailMixin:
    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        users = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            users = users.exclude(pk=self.instance.pk)
        if users.exists():
            raise forms.ValidationError("Этот имейл уже зарегистрирован.")
        return email


class RegistrationForm(EmailMixin, forms.ModelForm):
    password = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("name", "surname", "email")

    def clean(self):
        data = super().clean()
        candidate = User(
            name=data.get("name", ""), surname=data.get("surname", ""), email=data.get("email", "")
        )
        if data.get("password"):
            try:
                password_validation.validate_password(data["password"], candidate)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Имейл", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    password = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user = None

    def clean(self):
        data = super().clean()
        if data.get("email") and data.get("password"):
            self.user = authenticate(
                self.request, email=data["email"].strip().lower(), password=data["password"]
            )
            if self.user is None:
                raise forms.ValidationError("Неверный имейл или пароль")
        return data


class ProfileForm(EmailMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("name", "surname", "email", "avatar", "about", "phone", "github_url")
        widgets = {
            "avatar": forms.FileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
            "about": forms.Textarea(attrs={"rows": 4, "maxlength": 256}),
            "phone": forms.TextInput(attrs={"placeholder": "+79001234567"}),
        }

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get("phone"))
        if phone and User.objects.filter(phone=phone).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Этот номер телефона уже используется.")
        return phone

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if not avatar or not hasattr(avatar, "content_type"):
            return avatar
        if avatar.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Изображение должно быть не больше 5 МБ.")
        try:
            with Image.open(avatar) as picture:
                if picture.width * picture.height > 20_000_000:
                    raise forms.ValidationError(
                        "Размер изображения должен быть не больше 20 мегапикселей."
                    )
                picture = ImageOps.exif_transpose(picture).convert("RGB")
                picture.thumbnail((512, 512))
                output = BytesIO()
                picture.save(output, "PNG")
        except (OSError, ValueError, Image.DecompressionBombError):
            raise forms.ValidationError("Загрузите корректное изображение.") from None
        return ContentFile(output.getvalue(), name=f"{uuid4().hex}.png")


class AdminUserCreationForm(EmailMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "name", "surname")


class AdminUserChangeForm(EmailMixin, UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone"))

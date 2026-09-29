from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from .forms import LoginForm, ProfileForm, RegistrationForm
from .models import User


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("projects:list")
    form = RegistrationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error("email", "Этот имейл уже зарегистрирован.")
        else:
            messages.success(request, "Аккаунт создан. Войдите с имейлом и паролем.")
            return redirect("users:login")
    return render(request, "users/register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def login(request):
    if request.user.is_authenticated:
        return redirect("projects:list")
    form = LoginForm(request.POST if request.method == "POST" else None, request=request)
    next_url = request.POST.get("next", request.GET.get("next", ""))
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.user)
        if url_has_allowed_host_and_scheme(
            next_url, {request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect("projects:list")
    return render(request, "users/login.html", {"form": form, "next": next_url})


@login_required
@require_http_methods(["GET", "POST"])
def logout(request):
    if request.method == "POST":
        auth_logout(request)
        return redirect("projects:list")
    return render(request, "users/logout.html")


def participants(request):
    people = User.objects.all()
    page = Paginator(people, 12).get_page(request.GET.get("page"))
    return render(
        request, "users/participants.html", {"participants": page.object_list, "page_obj": page}
    )


def detail(request, pk):
    person = get_object_or_404(User.objects.prefetch_related("owned_projects__participants"), pk=pk)
    return render(request, "users/user-details.html", {"user": person})


@login_required
@require_http_methods(["GET", "POST"])
def edit_profile(request):
    form = ProfileForm(
        request.POST if request.method == "POST" else None,
        request.FILES or None,
        instance=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error(None, "Этот имейл или телефон уже используется.")
        else:
            messages.success(request, "Профиль сохранён.")
            return redirect(request.user)
    return render(request, "users/edit_profile.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def change_password(request):
    form = PasswordChangeForm(request.user, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Пароль изменён.")
        return redirect(user)
    return render(request, "users/change_password.html", {"form": form})

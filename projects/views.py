import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import ProjectForm
from .models import Project, Skill


def project_list(request):
    projects = Project.objects.select_related("owner").prefetch_related("participants", "skills")
    skill = request.GET.get("skill", "").strip()
    if skill:
        projects = projects.filter(skills__name=skill).distinct()
    page = Paginator(projects, 12).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "projects/project_list.html",
        {
            "projects": page.object_list,
            "page_obj": page,
            "active_skill": skill,
            "all_skills": Skill.objects.values_list("name", flat=True),
            "query_prefix": query.urlencode() + "&" if query else "",
        },
    )


@ensure_csrf_cookie
def detail(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("owner").prefetch_related("participants", "skills"), pk=pk
    )
    return render(request, "projects/project-details.html", {"project": project})


@login_required
@require_http_methods(["GET", "POST"])
def create(request):
    form = ProjectForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            project.participants.add(request.user)
        return redirect(project)
    return render(request, "projects/create-project.html", {"form": form, "is_edit": False})


@login_required
@require_http_methods(["GET", "POST"])
def edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if project.owner_id != request.user.pk:
        raise PermissionDenied
    form = ProjectForm(request.POST if request.method == "POST" else None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(project)
    return render(
        request, "projects/create-project.html", {"form": form, "is_edit": True, "project": project}
    )


def api_error(message, status=400):
    return JsonResponse({"status": "error", "error": message}, status=status)


def authorized_project(request, pk, owner_only=False):
    # Call inside atomic(): row locks serialize concurrent participation/skill changes.
    if not request.user.is_authenticated:
        return None, api_error("Войдите в аккаунт.", 401)
    project = Project.objects.select_for_update().filter(pk=pk).first()
    if project is None:
        return None, api_error("Проект не найден.", 404)
    if owner_only and project.owner_id != request.user.pk:
        return None, api_error("Изменять проект может только автор.", 403)
    return project, None


@require_POST
@transaction.atomic
def complete(request, pk):
    project, error = authorized_project(request, pk, owner_only=True)
    if error is not None:
        return error
    if project.status != Project.Status.OPEN:
        return api_error("Проект уже завершён.", 409)
    project.status = Project.Status.CLOSED
    project.save(update_fields=["status"])
    return JsonResponse({"status": "ok", "project_status": project.status})


@require_POST
@transaction.atomic
def toggle_participate(request, pk):
    project, error = authorized_project(request, pk)
    if error is not None:
        return error
    if project.owner_id == request.user.pk:
        return api_error("Автор всегда остаётся участником проекта.", 409)
    participating = project.participants.filter(pk=request.user.pk).exists()
    if participating:
        project.participants.remove(request.user)
    elif project.status == Project.Status.CLOSED:
        return api_error("Нельзя присоединиться к завершённому проекту.", 409)
    else:
        project.participants.add(request.user)
    return JsonResponse(
        {"status": "ok", "participant": not participating, "count": project.participants.count()}
    )


@require_GET
def skills(request):
    prefix = request.GET.get("q", "").strip()
    matches = Skill.objects.filter(name__istartswith=prefix)[:10]
    return JsonResponse(list(matches.values("id", "name")), safe=False)


@require_POST
@transaction.atomic
def add_skill(request, pk):
    project, error = authorized_project(request, pk, owner_only=True)
    if error is not None:
        return error
    try:
        data = (
            json.loads(request.body) if request.content_type == "application/json" else request.POST
        )
    except (ValueError, UnicodeDecodeError):
        return api_error("Некорректный JSON.")
    if not isinstance(data, dict) or ("name" in data) == ("skill_id" in data):
        return api_error("Передайте либо name, либо skill_id.")
    created = False
    if "skill_id" in data:
        raw_id = data["skill_id"]
        if isinstance(raw_id, bool) or not str(raw_id).isdigit() or len(str(raw_id)) > 18:
            return api_error("Некорректный идентификатор навыка.")
        skill = Skill.objects.filter(pk=int(raw_id)).first()
        if skill is None:
            return api_error("Навык не найден.", 404)
    else:
        name = data["name"]
        if not isinstance(name, str):
            return api_error("Название навыка должно быть строкой.")
        name = " ".join(name.split())
        if not name or len(name) > 124:
            return api_error("Название навыка должно содержать от 1 до 124 символов.")
        skill = Skill.objects.filter(name__iexact=name).first()
        if skill is None:
            try:
                with transaction.atomic():
                    skill = Skill.objects.create(name=name)
                    created = True
            except IntegrityError:
                skill = Skill.objects.get(name__iexact=name)
    added = not project.skills.filter(pk=skill.pk).exists()
    project.skills.add(skill)
    return JsonResponse(
        {
            "status": "ok",
            "id": skill.pk,
            "skill_id": skill.pk,
            "name": skill.name,
            "created": created,
            "added": added,
        }
    )


@require_POST
@transaction.atomic
def remove_skill(request, pk, skill_id):
    project, error = authorized_project(request, pk, owner_only=True)
    if error is not None:
        return error
    if not project.skills.filter(pk=skill_id).exists():
        return api_error("Этот навык не добавлен в проект.", 404)
    project.skills.remove(skill_id)
    return JsonResponse({"status": "ok"})

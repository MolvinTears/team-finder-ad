import json
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from users.models import User

from .models import Project, Skill


class ProjectTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = tempfile.TemporaryDirectory()
        cls.config = override_settings(
            MEDIA_ROOT=cls.media.name,
            PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
        )
        cls.config.enable()

    @classmethod
    def tearDownClass(cls):
        cls.config.disable()
        cls.media.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.owner = User.objects.create_user(
            "owner@example.com", "password", name="Автор", surname="Тест"
        )
        self.other = User.objects.create_user(
            "other@example.com", "password", name="Гость", surname="Тест"
        )
        self.project = Project.objects.create(name="Первый проект", owner=self.owner)
        self.project.participants.add(self.owner)
        self.base = self.project.get_absolute_url()

    def post_json(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def test_public_lists_details_and_root(self):
        self.assertRedirects(self.client.get("/"), "/projects/list/")
        self.assertRedirects(
            self.client.get("/project/list/?skill=Python"), "/projects/list/?skill=Python"
        )
        self.assertEqual(self.client.get(self.base).status_code, 200)
        self.assertContains(self.client.get(self.base), "Необходимые навыки")
        self.assertNotContains(self.client.get(self.base), 'id="add-skill-btn"')

    def test_create_sets_owner_and_joins_them(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            "/projects/create-project/",
            {
                "name": "Новый проект",
                "description": "Описание",
                "github_url": "https://github.com/example/repo",
                "status": "open",
                "owner": self.other.pk,
            },
        )
        new = Project.objects.get(name="Новый проект")
        self.assertRedirects(response, new.get_absolute_url())
        self.assertEqual(new.owner, self.owner)
        self.assertIn(self.owner, new.participants.all())

    def test_create_and_edit_require_authentication_and_ownership(self):
        self.assertEqual(self.client.get("/projects/create-project/").status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.base + "edit/").status_code, 403)
        self.assertEqual(self.client.post(self.base + "edit/", {"name": "Hacked"}).status_code, 403)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Первый проект")

    def test_edit_prefilled_and_saves(self):
        self.client.force_login(self.owner)
        form = self.client.get(self.base + "edit/").context["form"]
        self.assertEqual(form.initial["name"], self.project.name)
        response = self.client.post(
            self.base + "edit/",
            {"name": "Изменён", "description": "", "status": "closed", "github_url": ""},
        )
        self.assertRedirects(response, self.base)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "closed")
        self.assertEqual(self.project.name, "Изменён")

    def test_invalid_project_fields(self):
        self.client.force_login(self.owner)
        for data in [
            {"name": "", "status": "open"},
            {"name": "x" * 201, "status": "open"},
            {"name": "x", "status": "invalid"},
            {"name": "x", "status": "open", "github_url": "https://evil.example"},
        ]:
            response = self.client.post("/projects/create-project/", data)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(Project.objects.count(), 1)

    def test_join_leave_and_owner_cannot_leave(self):
        self.client.force_login(self.other)
        for expected in [True, False]:
            response = self.client.post(self.base + "toggle-participate/")
            self.assertEqual(response.json()["participant"], expected)
            self.assertEqual(self.project.participants.filter(pk=self.other.pk).exists(), expected)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.base + "toggle-participate/").status_code, 409)
        self.assertIn(self.owner, self.project.participants.all())

    def test_complete_owner_only_and_blocks_new_participants(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.base + "complete/").status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.post(self.base + "complete/")
        self.assertEqual(response.json()["project_status"], "closed")
        self.assertEqual(self.client.post(self.base + "complete/").status_code, 409)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.base + "toggle-participate/").status_code, 409)
        self.assertNotContains(self.client.get(self.base), 'id="participate-btn"')

    def test_participant_may_leave_closed_project(self):
        self.project.participants.add(self.other)
        self.project.status = "closed"
        self.project.save()
        self.client.force_login(self.other)
        self.assertContains(self.client.get(self.base), "Отказаться от участия")
        self.assertFalse(self.client.post(self.base + "toggle-participate/").json()["participant"])

    def test_all_mutations_require_post_and_authentication(self):
        for path in ["complete/", "toggle-participate/", "skills/add/", "skills/1/remove/"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(self.base + path).status_code, 405)
                self.assertEqual(self.client.post(self.base + path).status_code, 401)

    def test_csrf_enforced_and_token_issued_on_detail(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(
            client.post(self.base + "skills/add/", {"name": "Python"}).status_code, 403
        )
        client.get(self.base)
        token = client.cookies["csrftoken"].value
        response = client.post(
            self.base + "skills/add/", {"name": "Python"}, HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, 200)

    def test_skill_add_create_reuse_duplicate_remove(self):
        self.client.force_login(self.owner)
        path = self.base + "skills/add/"
        first = self.post_json(path, {"name": "  Python  "}).json()
        self.assertTrue(first["created"])
        self.assertTrue(first["added"])
        repeated = self.post_json(path, {"name": "python"}).json()
        self.assertFalse(repeated["created"])
        self.assertFalse(repeated["added"])
        self.assertEqual(first["id"], repeated["id"])
        self.assertEqual(self.project.skills.count(), 1)
        remove = self.base + f"skills/{first['id']}/remove/"
        self.assertEqual(self.client.post(remove).status_code, 200)
        self.assertTrue(Skill.objects.filter(pk=first["id"]).exists())
        self.assertEqual(self.client.post(remove).status_code, 404)
        reused = self.post_json(path, {"skill_id": first["id"]}).json()
        self.assertFalse(reused["created"])
        self.assertTrue(reused["added"])

    def test_skill_permission_checked_before_creating_global_skill(self):
        self.client.force_login(self.other)
        response = self.post_json(self.base + "skills/add/", {"name": "Unauthorized"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Skill.objects.exists())
        self.assertEqual(self.client.post(self.base + "skills/1/remove/").status_code, 403)

    def test_skill_api_handles_invalid_json_values_and_missing_objects(self):
        self.client.force_login(self.owner)
        for data in [
            None,
            [],
            {},
            {"name": ""},
            {"name": " "},
            {"name": 1},
            {"name": "a" * 125},
            {"skill_id": -1},
            {"skill_id": True},
            {"skill_id": "9" * 40},
            {"name": "Python", "skill_id": 1},
        ]:
            with self.subTest(data=data):
                self.assertEqual(self.post_json(self.base + "skills/add/", data).status_code, 400)
        self.assertEqual(
            self.client.post(
                self.base + "skills/add/", "{", content_type="application/json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post_json(self.base + "skills/add/", {"skill_id": 999999}).status_code, 404
        )
        self.assertEqual(
            self.post_json("/projects/999999/skills/add/", {"name": "Python"}).status_code, 404
        )

    def test_autocomplete_prefix_order_and_limit(self):
        for number in reversed(range(13)):
            Skill.objects.create(name=f"Python {number:02d}")
        Skill.objects.create(name="JavaScript")
        response = self.client.get("/projects/skills/?q=py")
        names = [skill["name"] for skill in response.json()]
        self.assertEqual(names, [f"Python {number:02d}" for number in range(10)])
        self.assertEqual(self.client.get("/projects/skills/?q=not-found").json(), [])

    def test_filter_is_exact_paginated_and_retained_in_page_links(self):
        skill = Skill.objects.create(name="C++ & Python")
        for number in range(13):
            project = Project.objects.create(name=f"Проект {number}", owner=self.owner)
            project.skills.add(skill)
        response = self.client.get("/projects/list/", {"skill": skill.name})
        page = response.context["page_obj"]
        self.assertEqual(len(page), 12)
        self.assertEqual(page.paginator.count, 13)
        self.assertEqual(page[0].name, "Проект 12")
        self.assertEqual(response.context["active_skill"], skill.name)
        self.assertIn("skill=C%2B%2B+%26+Python", response.context["query_prefix"])
        self.assertContains(response, "C%2B%2B%20%26%20Python")
        self.assertEqual(
            len(self.client.get("/projects/list/", {"skill": "C++"}).context["page_obj"]), 0
        )
        self.assertEqual(
            len(
                self.client.get("/projects/list/", {"skill": skill.name, "page": 2}).context[
                    "page_obj"
                ]
            ),
            1,
        )

    def test_user_text_is_escaped(self):
        self.project.name = "<script>alert(1)</script>"
        self.project.save()
        self.assertContains(self.client.get(self.base), "&lt;script&gt;")
        self.assertNotContains(self.client.get(self.base), "<script>alert(1)</script>")

    def test_missing_pages_are_404(self):
        self.assertEqual(self.client.get("/projects/999999/").status_code, 404)
        self.assertEqual(self.client.get("/users/999999/").status_code, 404)

    def test_seed_is_repeatable_and_users_have_projects(self):
        out = StringIO()
        for _ in range(2):
            call_command("seed_demo", password="Demo-password-2026!", stdout=out)
        self.assertEqual(Project.objects.count(), 17)
        for email in [
            "anna@example.com",
            "max@example.com",
            "maria@example.com",
            "ivan@example.com",
        ]:
            self.assertEqual(User.objects.get(email=email).owned_projects.count(), 4)

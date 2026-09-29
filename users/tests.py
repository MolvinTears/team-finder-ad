import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from PIL import Image

from .forms import ProfileForm
from .validators import validate_github

User = get_user_model()
PASSWORD = "Test-Strong-Password-47!"


class UserTests(TestCase):
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
        self.user = User.objects.create_user(
            "anna@example.com",
            PASSWORD,
            name="Анна",
            surname="Соколова",
        )

    def profile_data(self, **overrides):
        data = {
            "name": "Анна",
            "surname": "Соколова",
            "email": self.user.email,
            "phone": "",
            "about": "Описание",
            "github_url": "",
        }
        data.update(overrides)
        return data

    def test_user_created_with_hashed_password_and_generated_avatar(self):
        self.assertTrue(self.user.check_password(PASSWORD))
        self.assertNotEqual(self.user.password, PASSWORD)
        with self.user.avatar.open("rb") as file:
            image = Image.open(file)
            self.assertEqual(image.size, (256, 256))
            self.assertGreater(len(image.getcolors(maxcolors=65536)), 1)

    def test_registration_redirects_to_login(self):
        response = self.client.post(
            "/users/register/",
            {
                "name": "Борис",
                "surname": "Иванов",
                "email": "BORIS@Example.com",
                "password": PASSWORD,
            },
        )
        self.assertRedirects(response, "/users/login/")
        registered = User.objects.get(email="boris@example.com")
        self.assertTrue(registered.avatar)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_registration_rejects_missing_fields_weak_and_duplicate_email(self):
        samples = [
            {},
            {
                "name": "Анна",
                "surname": "Соколова",
                "email": "ANNA@example.com",
                "password": PASSWORD,
            },
            {
                "name": "Борис",
                "surname": "Иванов",
                "email": "new@example.com",
                "password": "12345678",
            },
            {"name": " ", "surname": "Иванов", "email": "new@example.com", "password": PASSWORD},
        ]
        for data in samples:
            with self.subTest(data=data):
                response = self.client.post("/users/register/", data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_login_is_case_insensitive(self):
        response = self.client.post(
            "/users/login/", {"email": "ANNA@EXAMPLE.COM", "password": PASSWORD}
        )
        self.assertRedirects(response, "/projects/list/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_bad_credentials_and_blocked_account(self):
        for active, password in [(True, "wrong"), (False, PASSWORD)]:
            self.user.is_active = active
            self.user.save()
            response = self.client.post(
                "/users/login/", {"email": self.user.email, "password": password}
            )
            self.assertContains(response, "Неверный имейл или пароль")
            self.assertNotIn("_auth_user_id", self.client.session)

    def test_next_is_local_only(self):
        for target, destination in [
            ("/projects/create-project/", "/projects/create-project/"),
            ("https://evil.example/", "/projects/list/"),
            ("//evil.example/", "/projects/list/"),
        ]:
            self.client.logout()
            response = self.client.post(
                "/users/login/",
                {
                    "email": self.user.email,
                    "password": PASSWORD,
                    "next": target,
                },
            )
            self.assertRedirects(response, destination)

    def test_profile_changes_only_after_valid_submit_and_url_is_stable(self):
        self.client.force_login(self.user)
        original = self.user.get_absolute_url()
        self.client.get("/users/edit-profile/?name=changed")
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "Анна")
        response = self.client.post(
            "/users/edit-profile/", self.profile_data(name="Аня", email="new@example.com")
        )
        self.assertRedirects(response, original)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "Аня")
        self.assertEqual(self.user.email, "new@example.com")

    def test_phone_normalization_and_uniqueness(self):
        form = ProfileForm(self.profile_data(phone="89001234567"), instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "+79001234567")
        other = User.objects.create_user(
            "other@example.com", PASSWORD, name="Олег", surname="Котов"
        )
        data = self.profile_data(email=other.email, phone="+79001234567")
        duplicate = ProfileForm(data, instance=other)
        self.assertFalse(duplicate.is_valid())
        self.assertIn("phone", duplicate.errors)

    def test_invalid_phone_and_about(self):
        for phone in ["79001234567", "123", "+7 900 1234567", "+790012345678", "+7abcdefghij"]:
            form = ProfileForm(self.profile_data(phone=phone), instance=self.user)
            self.assertFalse(form.is_valid())
            self.assertIn("phone", form.errors)
        form = ProfileForm(self.profile_data(about="я" * 257), instance=self.user)
        self.assertFalse(form.is_valid())

    def test_avatar_upload_is_reencoded_and_invalid_image_rejected(self):
        stream = BytesIO()
        Image.new("RGB", (800, 400), "red").save(stream, "JPEG")
        upload = SimpleUploadedFile("photo.jpg", stream.getvalue(), content_type="image/jpeg")
        form = ProfileForm(self.profile_data(), {"avatar": upload}, instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        with user.avatar.open("rb") as file:
            image = Image.open(file)
            self.assertEqual(image.format, "PNG")
            self.assertLessEqual(max(image.size), 512)
        bad = SimpleUploadedFile("bad.png", b"not an image", content_type="image/png")
        form = ProfileForm(self.profile_data(), {"avatar": bad}, instance=self.user)
        self.assertFalse(form.is_valid())

    def test_password_change_validates_old_and_keeps_session(self):
        self.client.force_login(self.user)
        new = "New-Strong-Password-84!"
        bad = self.client.post(
            "/users/change-password/",
            {
                "old_password": "wrong",
                "new_password1": new,
                "new_password2": new,
            },
        )
        self.assertTrue(bad.context["form"].errors)
        result = self.client.post(
            "/users/change-password/",
            {
                "old_password": PASSWORD,
                "new_password1": new,
                "new_password2": new,
            },
        )
        self.assertRedirects(result, self.user.get_absolute_url())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new))
        self.assertIn("_auth_user_id", self.client.session)

    def test_profile_and_list_are_public_but_edit_requires_login(self):
        self.assertEqual(self.client.get(self.user.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get("/users/list/").status_code, 200)
        for url in ["/users/edit-profile/", "/users/change-password/"]:
            self.assertRedirects(self.client.get(url), "/users/login/?next=" + url)

    def test_other_profile_does_not_show_edit_controls(self):
        visitor = User.objects.create_user(
            "visitor@example.com", PASSWORD, name="Гость", surname="Тест"
        )
        self.client.force_login(visitor)
        response = self.client.get(self.user.get_absolute_url())
        self.assertNotContains(response, ">Редактировать<")
        self.assertEqual(response.context["user"], self.user)
        self.assertEqual(response.wsgi_request.user, visitor)

    def test_users_newest_first_and_twelve_per_page(self):
        for number in range(13):
            User.objects.create_user(
                f"user{number}@example.com", PASSWORD, name="Участник", surname=str(number)
            )
        response = self.client.get("/users/list/")
        self.assertEqual(len(response.context["page_obj"]), 12)
        ids = [user.pk for user in response.context["page_obj"]]
        self.assertEqual(ids, sorted(ids, reverse=True))
        self.assertEqual(len(self.client.get("/users/list/?page=2").context["page_obj"]), 2)

    def test_github_validator_rejects_similar_hosts(self):
        for url in ["https://github.com/user/repo", "http://www.github.com/user"]:
            validate_github(url)
        for url in [
            "https://github.com.evil.test/repo",
            "https://evilgithub.com",
            "javascript:alert(1)",
            "https://user@github.com/repo",
        ]:
            with self.subTest(url=url), self.assertRaises(ValidationError):
                validate_github(url)

    def test_database_enforces_case_insensitive_email(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create(
                [
                    User(
                        email="ANNA@EXAMPLE.COM",
                        name="X",
                        surname="Y",
                        password="unused",
                        avatar="avatars/test.png",
                    )
                ]
            )

    def test_superuser_and_admin_pages(self):
        admin = User.objects.create_superuser(
            "admin@example.com", PASSWORD, name="Админ", surname="Тест"
        )
        self.assertTrue(admin.is_superuser)
        self.client.force_login(admin)
        for url in [
            "/admin/",
            "/admin/users/user/",
            "/admin/users/user/add/",
            "/admin/projects/project/",
        ]:
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_logout_requires_post_and_csrf(self):
        self.client.force_login(self.user)
        self.client.get("/users/logout/")
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.post("/users/logout/"), "/projects/list/")
        self.assertNotIn("_auth_user_id", self.client.session)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post("/users/logout/").status_code, 403)

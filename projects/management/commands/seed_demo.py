from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from projects.models import Project, Skill
from users.models import User


class Command(BaseCommand):
    help = (
        "Создать четыре демонстрационных аккаунта и 16 проектов без изменения существующих данных."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password", required=True, help="Пароль только для новых демоаккаунтов."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        if len(password) < 8:
            raise CommandError("Укажите пароль не короче восьми символов.")
        profiles = [
            ("anna", "Анна", "Соколова", "Python-разработчик. Создаю полезные сервисы."),
            ("max", "Максим", "Волков", "Фронтенд-разработчик, люблю понятные интерфейсы."),
            ("maria", "Мария", "Орлова", "Дизайнер и исследователь пользовательского опыта."),
            ("ivan", "Иван", "Петров", "Инженер данных. Ищу команду для пет-проектов."),
        ]
        topics = [
            (
                "Зелёный город",
                "Карта пунктов переработки и экологических инициатив.",
                ["Python", "Django", "PostgreSQL"],
            ),
            (
                "Книжный клуб",
                "Площадка для совместного чтения и обсуждения книг.",
                ["JavaScript", "React", "UX/UI"],
            ),
            (
                "Маршруты выходного дня",
                "Сервис коротких путешествий по интересным местам.",
                ["Python", "UX/UI"],
            ),
            (
                "Учимся вместе",
                "Планировщик учебных встреч и обмена опытом.",
                ["Django", "PostgreSQL"],
            ),
        ]
        people = []
        for login, name, surname, about in profiles:
            user = User.objects.filter(email=f"{login}@example.com").first()
            if user is None:
                user = User.objects.create_user(
                    email=f"{login}@example.com",
                    password=password,
                    name=name,
                    surname=surname,
                    about=about,
                )
            people.append(user)
        for index, owner in enumerate(people):
            for number, (title, description, skill_names) in enumerate(topics):
                project, created = Project.objects.get_or_create(
                    owner=owner,
                    name=f"{title} · {owner.name}",
                    defaults={
                        "description": description,
                        "status": "closed" if index == 3 and number == 3 else "open",
                    },
                )
                if created:
                    project.participants.add(owner, people[(index + 1) % len(people)])
                    for name in skill_names:
                        skill, _ = Skill.objects.get_or_create(name=name)
                        project.skills.add(skill)
        self.stdout.write(
            self.style.SUCCESS(
                "Демо готово: anna, max, maria, ivan @example.com. "
                "Существующие данные и пароли сохранены."
            )
        )

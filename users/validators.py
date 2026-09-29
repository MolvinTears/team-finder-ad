import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def validate_github(value):
    if not value:
        return
    URLValidator(schemes=["https", "http"])(value)
    url = urlsplit(value)
    if (
        url.hostname not in {"github.com", "www.github.com"}
        or url.username
        or url.password
        or url.port
    ):
        raise ValidationError("Введите ссылку на github.com.", code="invalid_github")


def normalize_phone(value):
    if not value:
        return None
    if not re.fullmatch(r"(?:8|\+7)[0-9]{10}", value):
        raise ValidationError("Телефон должен быть в формате 8XXXXXXXXXX или +7XXXXXXXXXX.")
    return "+7" + value[-10:]

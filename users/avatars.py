import hashlib
from io import BytesIO
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont


def avatar_file(name):
    palette = ("#D5E6DD", "#D6DFED", "#E5DBED", "#EDDCCB", "#DFE4CB")
    color = palette[hashlib.sha256(name.encode()).digest()[0] % len(palette)]
    picture = Image.new("RGB", (256, 256), color)
    draw = ImageDraw.Draw(picture)
    font = ImageFont.truetype(
        str(settings.BASE_DIR / "static/fonts/Neue_Haas_Grotesk_Display_Pro_75_Bold.otf"), 130
    )
    letter = (name.strip()[:1] or "?").upper()
    draw.text((128, 126), letter, font=font, fill="#263445", anchor="mm")
    stream = BytesIO()
    picture.save(stream, format="PNG")
    return ContentFile(stream.getvalue(), name=f"{uuid4().hex}.png")

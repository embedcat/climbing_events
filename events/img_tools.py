import io
import os

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

POSTER_MAX_SIDE = 1600
POSTER_MAX_PIXELS = 50_000_000
POSTER_WEBP_QUALITY = 80


def compress_poster(file) -> ContentFile:
    """Уменьшает постер до POSTER_MAX_SIDE по длинной стороне и пережимает в WebP."""
    file.seek(0)
    with Image.open(file) as img:
        # JPEG сразу декодируется в уменьшенном масштабе — меньше памяти и CPU на больших фото
        img.draft(None, (POSTER_MAX_SIDE, POSTER_MAX_SIDE))
        ImageOps.exif_transpose(img, in_place=True)
        if img.mode in ('RGB', 'RGBA'):
            icc_profile = img.info.get('icc_profile')
        else:
            # профиль исходного цветового пространства (например, CMYK) к RGB не подходит
            icc_profile = None
            img = img.convert('RGBA' if img.has_transparency_data else 'RGB')
        img.thumbnail((POSTER_MAX_SIDE, POSTER_MAX_SIDE))
        buf = io.BytesIO()
        img.save(buf, format='WEBP', quality=POSTER_WEBP_QUALITY, icc_profile=icc_profile)
    name = os.path.splitext(os.path.basename(file.name))[0] + '.webp'
    return ContentFile(buf.getvalue(), name=name)


def is_poster_compressed(file) -> bool:
    return file.name.lower().endswith('.webp') and max(file.width, file.height) <= POSTER_MAX_SIDE

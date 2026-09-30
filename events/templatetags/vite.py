"""Подключение Vue-экранов, собранных Vite (каталог frontend/).

В разработке (VITE_DEV_SERVER задан) скрипты берутся с dev-сервера Vite, в проде — из собранного манифеста.
"""
import json
import logging
from functools import lru_cache

from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.html import format_html, format_html_join

register = template.Library()
logger = logging.getLogger(settings.LOGGER)

STATIC_PREFIX = 'events/vue/'


@lru_cache(maxsize=1)
def _load_manifest_cached(path: str) -> dict:
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _load_manifest() -> dict:
    path = str(settings.VITE_MANIFEST)
    if settings.DEBUG:
        # в разработке сборка перезаписывается (vite build --watch), поэтому кеш не нужен
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return _load_manifest_cached(path)


def _collect(manifest: dict, name: str, seen: set) -> tuple:
    """Файлы точки входа: (js чанков-зависимостей, css, сам скрипт)"""
    chunk = manifest[name]
    css, imports = list(chunk.get('css', [])), []
    for dep in chunk.get('imports', []):
        if dep in seen:
            continue
        seen.add(dep)
        dep_imports, dep_css, _ = _collect(manifest, dep, seen)
        imports += dep_imports + [manifest[dep]['file']]
        css += dep_css
    return imports, css, chunk['file']


@register.simple_tag
def vite_entry(name: str):
    """ {% vite_entry 'src/entries/entry.ts' %}: скрипт экрана со стилями и предзагрузкой чанков """
    dev_server = settings.VITE_DEV_SERVER.rstrip('/')
    if dev_server:
        # dev-сервер отдаёт модули под тем же base, что и сборка (frontend/vite.config.ts)
        base = settings.STATIC_URL.lstrip('/') + STATIC_PREFIX
        return format_html(
            '<script type="module" src="{0}/{1}@vite/client"></script>'
            '<script type="module" src="{0}/{1}{2}"></script>', dev_server, base, name)
    try:
        manifest = _load_manifest()
        imports, css, script = _collect(manifest, name, {name})
    except (OSError, KeyError, ValueError):
        logger.exception('Не удалось подключить Vue-экран %s: нет сборки frontend (vite build)', name)
        if settings.DEBUG:
            raise
        return ''
    return (
        format_html_join('', '<link rel="stylesheet" href="{}">', ((static(STATIC_PREFIX + f),) for f in css))
        + format_html_join('', '<link rel="modulepreload" href="{}">',
                           ((static(STATIC_PREFIX + f),) for f in imports))
        + format_html('<script type="module" src="{}"></script>', static(STATIC_PREFIX + script))
    )

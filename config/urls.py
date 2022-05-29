import debug_toolbar
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path

from config import settings

handler404 = 'events.views.page_not_found_view'
handler500 = 'events.views.error_view'

urlpatterns = [
    path('', include('events.urls')),
    path('dja/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),
    re_path(r'^maintenance-mode/', include('maintenance_mode.urls')),
    path('accounts/', include('allauth.urls')),
]

if settings.USE_DJDT:
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

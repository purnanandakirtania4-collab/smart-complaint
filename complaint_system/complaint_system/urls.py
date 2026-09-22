import os

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as django_media_serve


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('complaints.urls')),
]


urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)
# User-uploaded media. For this small Railway deployment we can serve media
# through Django while the files live on a persistent Railway Volume.
# For larger traffic, move media to S3/Cloudinary and remove this route.
SERVE_MEDIA_WITH_DJANGO = os.environ.get(
    "SERVE_MEDIA_WITH_DJANGO",
    "True",
).lower() == "true"

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
elif SERVE_MEDIA_WITH_DJANGO:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            django_media_serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]

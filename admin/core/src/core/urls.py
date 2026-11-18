from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from app.forms import DjangoAdminConnexionForm

admin.site.login_form = DjangoAdminConnexionForm

urlpatterns = [
    path('admin/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),
    path('', include('moderation.urls')),
    path('', include('partners.urls')),
    path('', include('newsletter.urls')),
    path('', include('transport.urls')),
    path('', include('contactmessages.urls')),
    path('', include('parts.urls')),
    path('', include('analytics_live.urls')),
    path('', include('app.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

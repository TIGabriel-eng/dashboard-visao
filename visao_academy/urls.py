from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from core.views import CustomTokenObtainPairView, CookieTokenRefreshView, admin_backup_database, admin_restore_database

urlpatterns = [
    path('', lambda request: redirect('/admin/login/?next=/admin/'), name='root'),
    path('admin/', admin.site.urls),
    path('admin/backup-database/', admin_backup_database, name='backup_database'),
    path('admin/restore-database/', admin_restore_database, name='restore_database'),
    path('api/', include('core.urls')),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
]

if settings.DEBUG and settings.MEDIA_URL.startswith('/'):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

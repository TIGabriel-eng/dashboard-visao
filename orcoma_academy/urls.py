from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from core.views import CustomTokenObtainPairView, admin_backup_database, admin_restore_database
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('', lambda request: redirect('/admin/login/?next=/admin/'), name='root'),
    path('admin/', admin.site.urls),
    path('admin/backup-database/', admin_backup_database, name='backup_database'),
    path('admin/restore-database/', admin_restore_database, name='restore_database'),
    path('api/', include('core.urls')),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

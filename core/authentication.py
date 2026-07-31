from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken


class CookieJWTAuthentication(JWTAuthentication):
    def get_header(self, request):
        # Primeiro tenta cookie, senão header Authorization
        header = request.COOKIES.get(settings.JWT_COOKIE)
        return f'Bearer {header}'.encode() if header else super().get_header(request)


def set_jwt_cookies(response, access, refresh=None):
    access_expires = timezone.now() + getattr(settings, 'JWT_COOKIE_MAX_AGE', timedelta(days=1))
    response.set_cookie(
        settings.JWT_COOKIE,
        access,
        expires=access_expires,
        httponly=getattr(settings, 'JWT_COOKIE_HTTPONLY', True),
        secure=getattr(settings, 'JWT_COOKIE_SECURE', False),
        samesite=getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax'),
        path=getattr(settings, 'JWT_COOKIE_PATH', '/'),
    )
    if refresh:
        refresh_lifetime = settings.SIMPLE_JWT.get('REFRESH_TOKEN_LIFETIME', timedelta(days=7))
        refresh_expires = timezone.now() + refresh_lifetime
        response.set_cookie(
            settings.JWT_COOKIE_REFRESH,
            refresh,
            expires=refresh_expires,
            httponly=getattr(settings, 'JWT_COOKIE_HTTPONLY', True),
            secure=getattr(settings, 'JWT_COOKIE_SECURE', False),
            samesite=getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax'),
            path=getattr(settings, 'JWT_COOKIE_PATH', '/'),
        )
    return response


def clear_jwt_cookies(response):
    response.delete_cookie(settings.JWT_COOKIE, path=getattr(settings, 'JWT_COOKIE_PATH', '/'))
    response.delete_cookie(settings.JWT_COOKIE_REFRESH, path=getattr(settings, 'JWT_COOKIE_PATH', '/'))
    return response
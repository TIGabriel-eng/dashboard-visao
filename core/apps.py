import sys

from django.apps import AppConfig


def create_default_admin(sender, **kwargs):
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        admin_password = 'Painel@2026TI'
        admin_usernames = ['administração.orcoma', 'administracao.orcoma']

        for username in admin_usernames:
            user, created = User.objects.get_or_create(username=username)
            if created or not user.is_superuser or not user.check_password(admin_password):
                user.set_password(admin_password)
                user.is_staff = True
                user.is_superuser = True
                user.email = ''
                user.save()
    except Exception:
        pass


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Modalidades'

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(create_default_admin, sender=self)
        if any(arg in sys.argv for arg in ['runserver', 'runserver_plus', 'uwsgi', 'gunicorn']):
            create_default_admin(sender=self)

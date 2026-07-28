from django.apps import AppConfig
import sys


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Modalidades'

    def ready(self):
        running_migrations = any(cmd in sys.argv for cmd in ['migrate', 'makemigrations'])
        if running_migrations:
            return
        if 'RUN_MAIN' in sys.argv or sys.argv[1:2] == ['runserver']:
            from core.scheduler import iniciar
            iniciar()
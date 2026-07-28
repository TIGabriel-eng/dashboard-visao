from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore, register_events


def verificar_eventos_job():
    from core.management.commands.enviar_lembretes_evento import Command
    Command().handle()


def iniciar():
    scheduler = BackgroundScheduler(timezone='America/Sao_Paulo')
    scheduler.add_jobstore(DjangoJobStore(), 'default')

    scheduler.add_job(
        verificar_eventos_job,
        trigger='interval',
        hours=1,
        id='verificar_eventos',
        replace_existing=True,
        misfire_grace_time=3600,
    )

    register_events(scheduler)
    scheduler.start()
    return scheduler
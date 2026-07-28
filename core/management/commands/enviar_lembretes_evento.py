from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Evento, Notificacao
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Envia lembretes de eventos que ocorrem em aproximadamente 24 horas'

    def handle(self, *args, **options):
        agora = timezone.now()
        inicio_janela = agora + timedelta(hours=23)
        fim_janela = agora + timedelta(hours=25)

        eventos = Evento.objects.filter(data__gte=inicio_janela, data__lte=fim_janela)

        if not eventos.exists():
            self.stdout.write(self.style.SUCCESS('Nenhum evento nas próximas 24h.'))
            return

        usuarios = User.objects.filter(is_active=True)
        criadas = 0

        for evento in eventos:
            hora = evento.data.astimezone(timezone.get_current_timezone()).strftime('%H:%M')
            for usuario in usuarios:
                ja_tem = Notificacao.objects.filter(
                    usuario=usuario,
                    tipo='evento',
                    mensagem__contains=evento.titulo,
                    created_at__date=timezone.now().date(),
                ).exists()
                if ja_tem:
                    continue
                Notificacao.objects.create(
                    usuario=usuario,
                    titulo='Lembrete de Evento!',
                    mensagem=f'Amanhã: {evento.titulo} às {hora}',
                    tipo='evento',
                    link='/eventos',
                )
                criadas += 1

        self.stdout.write(self.style.SUCCESS(
            f'{criadas} lembretes criados para {eventos.count()} evento(s).'
        ))
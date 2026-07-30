import json
import os
import secrets

from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from core.models import Perfil


DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data',
    'equipe_admin.json',
)


class Command(BaseCommand):
    help = 'Importa a equipe de administradores Orcoma a partir de data/equipe_admin.json'

    def add_arguments(self, parser):
        parser.add_argument(
            '--forcar',
            action='store_true',
            help='Atualiza dados de usuários que já existem (perfil, cargo, unidade)'
        )

    def handle(self, *args, **options):
        if not os.path.exists(DATA_FILE):
            self.stdout.write(self.style.ERROR(f'Arquivo não encontrado: {DATA_FILE}'))
            self.stdout.write('Crie o arquivo data/equipe_admin.json com os dados da equipe.')
            return

        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            equipe = json.load(f)

        forcar = options['forcar']
        criados = 0
        atualizados = 0
        ignorados = 0
        erros = 0

        for data in equipe:
            email = data['email'].strip()
            username = email.split('@')[0]
            username = username.lower()

            try:
                user = User.objects.filter(username=username).first()

                if user:
                    if forcar:
                        user.first_name = data['first_name'].strip()
                        user.last_name = data['last_name'].strip()
                        user.email = email
                        user.is_staff = True
                        user.is_superuser = True
                        user.save()

                        perfil = user.perfil
                        perfil.role = 'admin'
                        perfil.empresa = 'Orcoma'
                        perfil.cargo = data.get('cargo', '')
                        perfil.unidade = data.get('unidade', '')
                        perfil.save()

                        atualizados += 1
                        self.stdout.write(f'  Atualizado: {username}')
                    else:
                        ignorados += 1
                    continue

                senha = secrets.token_urlsafe(16)
                user = User(
                    username=username,
                    email=email,
                    first_name=data['first_name'].strip(),
                    last_name=data['last_name'].strip(),
                    is_staff=True,
                    is_superuser=True,
                )
                user.password = make_password(senha)
                user.save()

                perfil = user.perfil
                perfil.role = 'admin'
                perfil.empresa = 'Orcoma'
                perfil.cargo = data.get('cargo', '')
                perfil.unidade = data.get('unidade', '')
                perfil.save()

                criados += 1
                self.stdout.write(f'  Criado: {username}  |  Senha: {senha}')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Erro ao processar {username}: {e}'))
                erros += 1

        self.stdout.write()
        self.stdout.write(self.style.SUCCESS('=== RESUMO ==='))
        self.stdout.write(self.style.SUCCESS(f'Criados:    {criados}'))
        self.stdout.write(self.style.SUCCESS(f'Atualizados: {atualizados}'))
        self.stdout.write(self.style.ERROR(f'Erros:      {erros}'))

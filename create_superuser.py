import getpass
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'orcoma_academy.settings')

# Adiciona o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.contrib.auth.models import User

username = sys.argv[1] if len(sys.argv) > 1 else 'admin'
email = sys.argv[2] if len(sys.argv) > 2 else 'admin@orcoma.com.br'
password = os.environ.get('ADMIN_PASSWORD') or getpass.getpass('Senha do superusuario: ')

if not password:
    print('ERRO: defina a variavel ADMIN_PASSWORD ou informe a senha no prompt.')
    sys.exit(1)

if User.objects.filter(username=username).exists():
    print(f'Usuario "{username}" ja existe.')
else:
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'Superusuario "{username}" criado com sucesso!')
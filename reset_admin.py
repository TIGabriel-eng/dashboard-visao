import getpass
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'visao_academy.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User

password = os.environ.get('ADMIN_PASSWORD') or getpass.getpass('Nova senha do usuario admin: ')

if not password:
    print('ERRO: defina a variavel ADMIN_PASSWORD ou informe a senha no prompt.')
    sys.exit(1)

try:
    user = User.objects.get(username='admin')
    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print('Senha do usuario "admin" redefinida com sucesso.')
    print(f'is_staff: {user.is_staff}, is_superuser: {user.is_superuser}')
except User.DoesNotExist:
    print('Usuario "admin" nao encontrado')
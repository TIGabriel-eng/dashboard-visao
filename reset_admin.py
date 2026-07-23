import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'orcoma_academy.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User

try:
    user = User.objects.get(username='admin')
    user.set_password('***REMOVED***')
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print(f'Senha do usuario "admin" resetada para: ***REMOVED***')
    print(f'is_staff: {user.is_staff}, is_superuser: {user.is_superuser}')
except User.DoesNotExist:
    print('Usuario "admin" nao encontrado')
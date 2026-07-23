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
password = sys.argv[3] if len(sys.argv) > 3 else '***REMOVED***'

if User.objects.filter(username=username).exists():
    print(f'Usuario "{username}" ja existe.')
else:
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'Superusuario "{username}" criado com sucesso!')
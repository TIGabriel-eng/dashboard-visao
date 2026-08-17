import django, os, sys
os.environ['DJANGO_SETTINGS_MODULE']='visao_academy.settings'
sys.path.insert(0, os.path.dirname(__file__))
django.setup()
from django.contrib.auth.models import User
users = User.objects.all().values('id','username','email','is_staff','is_superuser')
for u in users:
    print(f"{u['id']}: {u['username']} ({u['email']}) staff={u['is_staff']} super={u['is_superuser']}")

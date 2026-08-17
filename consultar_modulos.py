"""Script temporário para consultar cursos e módulos."""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'visao_academy.settings')

# Carrega o .env se existir
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / '.env')

django.setup()

from core.models import Curso, Modulo

total_cursos = Curso.objects.count()
total_modulos = Modulo.objects.count()
print(f"Total de cursos: {total_cursos}")
print(f"Total de módulos: {total_modulos}")

curso_onboarding = Curso.objects.filter(titulo__icontains='onboarding').first()
if curso_onboarding:
    modulos = Modulo.objects.filter(curso=curso_onboarding).order_by('ordem')
    print(f"Curso onboarding encontrado: {curso_onboarding.titulo} (id={curso_onboarding.id})")
    print(f"Total de módulos: {modulos.count()}")
    print("\nOrdem dos módulos:")
    for m in modulos:
        print(f"  {m.ordem}. {m.titulo} (id={m.id}, ativo={m.ativo})")
else:
    print("Nenhum curso 'onboarding' encontrado")
    for c in Curso.objects.all()[:5]:
        mods = Modulo.objects.filter(curso=c).order_by('ordem')
        print(f"  Curso: {c.titulo} | Módulos: {mods.count()}")

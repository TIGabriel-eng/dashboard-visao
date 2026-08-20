from django.core.management.base import BaseCommand
from core.models import AcessoRoleAcademia, Ambiente


MAPPING = {
    'cliente_vex': ['Academy Vex', 'Academy Empresarial'],
    'empresário': ['Academy Empresarial'],
    'cliente_equipe': ['Academy Time'],
    'colaborador_vex': ['Academy Vex Visioners'],
}


class Command(BaseCommand):
    help = 'Configura as permissões de acesso por role e ambiente (AcessoRoleAcademia)'

    def handle(self, *args, **options):
        ambientes = {a.nome: a.pk for a in Ambiente.objects.all()}
        if not ambientes:
            self.stdout.write(self.style.ERROR('Nenhum ambiente cadastrado. Crie os ambientes primeiro.'))
            return

        total_criados = 0
        total_atualizados = 0
        for role, nomes in MAPPING.items():
            for nome_ambiente in nomes:
                pk = ambientes.get(nome_ambiente)
                if not pk:
                    self.stdout.write(self.style.WARNING(f"Ambiente '{nome_ambiente}' não encontrado. Ignorando."))
                    continue

                _, created = AcessoRoleAcademia.objects.update_or_create(
                    role=role,
                    academia_id=pk,
                    defaults={'ativo': True},
                )
                if created:
                    total_criados += 1
                else:
                    total_atualizados += 1

        self.stdout.write(self.style.SUCCESS(f'Setup concluído: {total_criados} criados, {total_atualizados} atualizados.'))
from django.setup import setup as django_setup

def setup_acesso_role_academia():
    """
    Script para configurar as permissões de acesso por role e ambiente.
    Deve ser executado via: python manage.py shell < backend/scripts/setup_acesso_role_academia.py
    ou integrado a um comando customizado do Django.
    """
    try:
        from core.models import AcessoRoleAcademia, Ambiente, Perfil
        from django.contrib.auth.models import User
    except ImportError as e:
        print(f"Erro ao importar modelos: {e}")
        return

    MAPPING = {
        'cliente_vex': ['Academy Vex', 'Academy Empresarial'],
        'empresário': ['Academy Empresarial'],
        'cliente_equipe': ['Academy Time'],
        'colaborador_vex': ['Academy Vex Visioners'],
        # admin e cliente_premium não precisam de entrada aqui,
        # pois o código já trata como acesso total.
    }

    ambientes = {a.nome: a.pk for a in Ambiente.objects.all()}
    if not ambientes:
        print("Nenhum ambiente cadastrado. Crie os ambientes primeiro.")
        return

    total_criados = 0
    total_atualizados = 0
    for role, nomes in MAPPING.items():
        for nome_ambiente in nomes:
            pk = ambientes.get(nome_ambiente)
            if not pk:
                print(f"Ambiente '{nome_ambiente}' não encontrado. Ignorando.")
                continue

            obj, created = AcessoRoleAcademia.objects.update_or_create(
                role=role,
                academia_id=pk,
                defaults={'ativo': True},
            )
            if created:
                total_criados += 1
            else:
                total_atualizados += 1

    print(f"Setup concluído: {total_criados} registros criados, {total_atualizados} atualizados.")

    # Opcional: garantir que roles com acesso total não tenham registros residuais
    for role in ['admin', 'gestor_orcoma', 'cliente_premium']:
        qs = AcessoRoleAcademia.objects.filter(role=role)
        if qs.exists():
            qs.delete()
            print(f"Registros residual de '{role}' removidos.")


if __name__ == '__main__':
    setup_acesso_role_academia()
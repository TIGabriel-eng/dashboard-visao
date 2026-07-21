from django.contrib.auth.models import AnonymousUser

from core.models import Ambiente, AcessoRoleAcademia, Perfil


ROLES_ACESSO_TOTAL = {'admin', 'gestor_orcoma', 'cliente_premium'}

PERMISSOES_PAPEL = {
    'cliente_orcoma': ['Academy Contábil', 'Academy Gestão Empresarial'],
    'empresario': ['Academy Gestão Empresarial'],
    'cliente_equipe': ['Academy Time'],
    'colaborador_orcoma': ['Academy Orcomakers'],
    'admin': None,  # acesso total
    'cliente_premium': None,  # acesso total menos Academy Orcomakers
}


def get_user_role(user):
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return 'visitor'
    perfil = getattr(user, 'perfil', None)
    if perfil:
        return perfil.role
    return 'visitor'


def get_academias_permitidas(user):
    if user and user.is_authenticated and user.is_superuser:
        return Ambiente.objects.filter(ativo=True)

    role = get_user_role(user)
    if role in ROLES_ACESSO_TOTAL:
        qs = Ambiente.objects.filter(ativo=True)
        if role == 'cliente_premium':
            qs = qs.exclude(nome__iexact='Academy Orcomakers')
        return qs

    nomes_permitidos = PERMISSOES_PAPEL.get(role, [])
    if not nomes_permitidos:
        return Ambiente.objects.none()

    return Ambiente.objects.filter(
        ativo=True,
        nome__in=nomes_permitidos,
    ).distinct()


def user_can_access_curso(curso, user):
    if curso.status != 'publicado':
        if not user or not user.is_authenticated or not user.is_staff:
            return False

    if curso.is_gratuito:
        return True

    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    role = get_user_role(user)
    if role in ROLES_ACESSO_TOTAL:
        return True

    roles_extras = curso.roles_extras or []
    if role in roles_extras:
        return True

    academias_permitidas = get_academias_permitidas(user)
    if not academias_permitidas.exists():
        return False

    if curso.academias_extras.filter(pk__in=academias_permitidas.values_list('pk', flat=True)).exists():
        return True

    if curso.ambiente_id and academias_permitidas.filter(pk=curso.ambiente_id).exists():
        return True

    return False


def filtrar_cursos_acessiveis(queryset, user):
    from django.db.models import Q

    if user and user.is_authenticated and (user.is_superuser or get_user_role(user) in ROLES_ACESSO_TOTAL):
        return queryset

    academias_ids = list(get_academias_permitidas(user).values_list('pk', flat=True))

    q = Q(is_gratuito=True)
    if academias_ids:
        q |= Q(ambiente_id__in=academias_ids)
        q |= Q(academias_extras__in=academias_ids)

    if user and user.is_authenticated:
        role = get_user_role(user)
        q |= Q(roles_extras__contains=[role])

    return queryset.filter(q).distinct()


def get_academias_permitidas_para_role(role):
    if role in ROLES_ACESSO_TOTAL:
        qs = Ambiente.objects.filter(ativo=True)
        if role == 'cliente_premium':
            qs = qs.exclude(nome__iexact='Academy Orcomakers')
        return qs
    nomes_permitidos = PERMISSOES_PAPEL.get(role, [])
    if not nomes_permitidos:
        return Ambiente.objects.none()
    return Ambiente.objects.filter(
        ativo=True,
        nome__in=nomes_permitidos,
    ).distinct()


def validar_role_planos(role, planos):
    if not planos:
        return None

    academias_permitidas = get_academias_permitidas_para_role(role)
    permitidas_ids = set(academias_permitidas.values_list('pk', flat=True))

    for plano in planos:
        for ambiente in plano.ambientes.all():
            if ambiente.pk not in permitidas_ids:
                return (
                    f'O perfil "{dict(Perfil.ROLE_CHOICES).get(role, role)}" '
                    f'não pode ser vinculado à academy "{ambiente.nome}" '
                    f'(plano "{plano.nome}").'
                )
    return None

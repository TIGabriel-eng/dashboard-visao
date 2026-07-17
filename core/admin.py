from django.contrib import admin, messages
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import redirect, get_object_or_404
from django.utils.html import format_html
from django.urls import path, reverse
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from .models import Curso, Video, Modulo, Material, Trilha, Evento, Novidade, LogAtividade, Cliente, CursoVisualizacao, Matricula, Plano, Ambiente, Perfil, Permissao, FormacaoAcademica, Habilidade, AssinaturaPlano
from .forms import CursoAdminForm

User = get_user_model()

admin.site.site_header = 'Orcoma Academy'
admin.site.site_title = 'Orcoma Academy - Admin'
admin.site.index_title = 'Painel Administrativo'
admin.site.site_url = None

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(Permissao)
class PermissaoAdmin(GroupAdmin):
    model = Permissao
    verbose_name = 'Permissão'
    verbose_name_plural = 'Permissões'
    change_form_template = 'admin/core/permissao/change_form.html'
    change_list_template = 'admin/core/permissao/change_list.html'
    list_display = ('name', 'quantidade_permissoes', 'quantidade_usuarios')
    search_fields = ('name',)
    fieldsets = (
        (None, {
            'fields': ('name',),
        }),
    )

    # ── Templates de Papéis Pré-configurados ──
    ROLE_TEMPLATES = {
        'administrador': {
            'name': 'Administrador',
            'icon': 'fa-solid fa-crown',
            'color': '#f59e0b',
            'description': 'Acesso total ao sistema',
            'codenames': '__all__',
        },
        'conteudo_criador': {
            'name': 'Conteúdo - Criador',
            'icon': 'fa-solid fa-pen-fancy',
            'color': '#3b82f6',
            'description': 'Adiciona e edita cursos, trilhas e novidades',
            'codenames': [
                'add_curso', 'change_curso', 'view_curso',
                'cadastrar_videos', 'editar_videos', 'excluir_videos', 'publicar_cursos',
                'add_trilha', 'change_trilha', 'view_trilha', 'gerenciar_trilhas',
                'add_novidade', 'change_novidade', 'view_novidade', 'gerenciar_novidades',
            ],
        },
        'conteudo_colaborador': {
            'name': 'Conteúdo - Colaborador',
            'icon': 'fa-solid fa-user-pen',
            'color': '#6366f1',
            'description': 'Apenas adiciona conteúdo',
            'codenames': [
                'add_curso', 'view_curso', 'cadastrar_videos',
                'add_trilha', 'view_trilha',
                'add_novidade', 'view_novidade',
            ],
        },
        'conteudo_editor': {
            'name': 'Conteúdo - Editor',
            'icon': 'fa-solid fa-globe',
            'color': '#8b5cf6',
            'description': 'Publica e gerencia conteúdo',
            'codenames': [
                'view_curso', 'change_curso', 'publicar_cursos',
                'view_trilha', 'change_trilha', 'gerenciar_trilhas',
                'view_novidade', 'change_novidade', 'gerenciar_novidades',
            ],
        },
        'comercial': {
            'name': 'Comercial',
            'icon': 'fa-solid fa-briefcase',
            'color': '#10b981',
            'description': 'Gerencia clientes, planos e ambientes',
            'codenames': [
                'add_cliente', 'change_cliente', 'delete_cliente', 'view_cliente',
                'add_plano', 'change_plano', 'view_plano', 'gerenciar_planos',
                'view_ambiente', 'gerenciar_ambientes',
                'view_perfil',
            ],
        },
        'rh': {
            'name': 'RH',
            'icon': 'fa-solid fa-users',
            'color': '#ec4899',
            'description': 'Relatórios de vídeos e formulários',
            'codenames': [
                'view_cursovisualizacao', 'add_cursovisualizacao',
                'view_logatividade',
                'view_matricula',
                'view_perfil',
            ],
        },
        'monitoramento': {
            'name': 'Monitoramento',
            'icon': 'fa-solid fa-chart-line',
            'color': '#14b8a6',
            'description': 'Logs, visualizações e eventos',
            'codenames': [
                'view_logatividade', 'ver_logs_atividade',
                'view_cursovisualizacao',
                'view_matricula',
                'add_evento', 'change_evento', 'view_evento', 'gerenciar_eventos',
            ],
        },
    }

    CATEGORIAS_PERMISSOES = {
        'Administração': {
            'icon': 'fa-solid fa-users-gear',
            'slug': 'administracao',
            'models': ['user', 'group', 'cliente', 'permissao', 'perfil', 'plano', 'ambiente'],
        },
        'Conteúdo': {
            'icon': 'fa-solid fa-book-open',
            'slug': 'conteudo',
            'models': ['curso', 'trilha', 'novidade'],
        },
        'Moderadores': {
            'icon': 'fa-solid fa-user-shield',
            'slug': 'moderadores',
            'models': ['evento', 'logatividade', 'cursovisualizacao', 'matricula'],
        },
    }

    PERM_NAME_MAP = {
        'Can add': 'Adicionar',
        'Can change': 'Editar',
        'Can delete': 'Excluir',
        'Can view': 'Visualizar',
    }

    MODEL_NAME_MAP = {
        'user': 'Usuário',
        'group': 'Grupo',
        'permission': 'Permissão',
        'log entry': 'Registro de log',
        'content type': 'Tipo de conteúdo',
        'session': 'Sessão',
    }

    CODENAME_MAP = {
        'add_': 'adicionar_',
        'change_': 'editar_',
        'delete_': 'excluir_',
        'view_': 'visualizar_',
    }

    def get_urls(self):
        custom_urls = [
            path(
                '<int:pk>/duplicar/',
                self.admin_site.admin_view(self.duplicar_grupo),
                name='core_permissao_duplicar',
            ),
            path(
                'criar-template/<str:template_key>/',
                self.admin_site.admin_view(self.criar_de_template),
                name='core_permissao_criar_template',
            ),
        ]
        return custom_urls + super().get_urls()

    # ── Colunas da listagem ──
    def quantidade_permissoes(self, obj):
        return obj.permissions.count()
    quantidade_permissoes.short_description = 'Permissões'

    def quantidade_usuarios(self, obj):
        return obj.user_set.count()
    quantidade_usuarios.short_description = 'Usuários'

    # ── Traduções ──
    def _translate_perm_name(self, perm_name):
        for eng, ptbr in self.PERM_NAME_MAP.items():
            if perm_name.startswith(eng):
                suffix = perm_name[len(eng):].strip()
                for model_eng, model_ptbr in self.MODEL_NAME_MAP.items():
                    if suffix.lower() == model_eng.lower():
                        suffix = model_ptbr
                        break
                return ptbr + ' ' + suffix if suffix else ptbr
        return perm_name

    def _translate_codename(self, codename):
        for eng_prefix, ptbr_prefix in self.CODENAME_MAP.items():
            if codename.startswith(eng_prefix):
                return ptbr_prefix + codename[len(eng_prefix):]
        return codename

    # ── Construção de categorias ──
    def _build_perm_categories(self, obj=None):
        all_perms = Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'content_type__model', 'codename'
        )
        selected_pks = set()
        if obj and obj.pk:
            selected_pks = set(obj.permissions.values_list('pk', flat=True))

        models_map = {}
        for p in all_perms:
            ct = p.content_type
            key = ct.model
            if key not in models_map:
                models_map[key] = {
                    'app_label': ct.app_label,
                    'object_name': ct.model,
                    'verbose_name': ct.name if hasattr(ct, 'name') else ct.model,
                    'permissions': [],
                }
            model_class = ct.model_class()
            if model_class and hasattr(model_class, '_meta'):
                models_map[key]['verbose_name'] = str(model_class._meta.verbose_name)
            models_map[key]['permissions'].append({
                'pk': p.pk,
                'codename': self._translate_codename(p.codename),
                'name': self._translate_perm_name(p.name),
                'selected': p.pk in selected_pks,
            })

        categories = []
        placed_models = set()

        for cat_name, cat_info in self.CATEGORIAS_PERMISSOES.items():
            models_list = []
            for model_name in cat_info['models']:
                if model_name in models_map:
                    entry = models_map[model_name].copy()
                    entry['permissions'] = list(models_map[model_name]['permissions'])
                    models_list.append(entry)
                    placed_models.add(model_name)
            if models_list:
                total = sum(len(m['permissions']) for m in models_list)
                categories.append({
                    'name': cat_name,
                    'slug': cat_info['slug'],
                    'icon': cat_info['icon'],
                    'total': total,
                    'models': models_list,
                })

        other_perms = []
        for model_name, model_data in models_map.items():
            if model_name not in placed_models:
                other_perms.extend(model_data['permissions'])
        if other_perms:
            categories.append({
                'name': 'Outros',
                'slug': 'outros',
                'icon': 'fa-solid fa-ellipsis',
                'total': len(other_perms),
                'models': [{
                    'app_label': 'other',
                    'object_name': 'other',
                    'verbose_name': 'Outras permissões',
                    'permissions': other_perms,
                }],
            })

        return categories

    # ── Dashboard (change_list_view) ──
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        groups = Permissao.objects.annotate(
            num_users=Count('user', distinct=True),
            num_perms=Count('permissions', distinct=True),
        ).order_by('name')

        stats = {
            'total_groups': groups.count(),
            'total_perms': Permission.objects.count(),
            'total_users': User.objects.filter(is_active=True).count(),
            'groups': groups,
        }
        extra_context['stats'] = stats
        extra_context['role_templates'] = self.ROLE_TEMPLATES
        return super().changelist_view(request, extra_context=extra_context)

    # ── Views de formulário ──
    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['perm_categories'] = self._build_perm_categories()
        extra_context['original_permissions'] = Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'content_type__model', 'codename'
        )
        extra_context['selected_permissions'] = set()
        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        extra_context['perm_categories'] = self._build_perm_categories(obj)
        extra_context['original_permissions'] = Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'content_type__model', 'codename'
        )
        extra_context['selected_permissions'] = set(
            obj.permissions.values_list('pk', flat=True)
        ) if obj else set()
        extra_context['all_users'] = User.objects.filter(is_active=True).order_by('username')
        extra_context['group_users'] = obj.user_set.all() if obj else User.objects.none()
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        perm_pks = request.POST.getlist('permissions')
        obj.permissions.set(perm_pks)

    # ── Atribuição rápida de usuários ──
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        user_pks = request.POST.getlist('group_users')
        if user_pks:
            obj.user_set.set(user_pks)

    # ── Duplicar Grupo ──
    def duplicar_grupo(self, request, pk):
        original = get_object_or_404(Permissao, pk=pk)
        novo_grupo = Permissao.objects.create(name=f'Cópia de {original.name}')
        perm_pks = original.permissions.values_list('pk', flat=True)
        novo_grupo.permissions.set(perm_pks)
        self.message_user(request, f'Grupo "{novo_grupo.name}" criado com {perm_pks.count()} permissões.')
        return redirect(reverse('admin:core_permissao_change', args=[novo_grupo.pk]))

    # ── Criar a partir de Template ──
    def criar_de_template(self, request, template_key):
        if template_key not in self.ROLE_TEMPLATES:
            self.message_user(request, 'Template inválido.', level=messages.ERROR)
            return redirect(reverse('admin:core_permissao_changelist'))

        tpl = self.ROLE_TEMPLATES[template_key]
        novo_grupo = Permissao.objects.create(name=tpl['name'])

        if tpl['codenames'] == '__all__':
            all_perms = Permission.objects.values_list('pk', flat=True)
            novo_grupo.permissions.set(all_perms)
        else:
            perm_pks = Permission.objects.filter(codename__in=tpl['codenames']).values_list('pk', flat=True)
            novo_grupo.permissions.set(perm_pks)

        self.message_user(request, f'Grupo "{novo_grupo.name}" criado com {novo_grupo.permissions.count()} permissões.')
        return redirect(reverse('admin:core_permissao_change', args=[novo_grupo.pk]))


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name = 'Perfil'
    verbose_name_plural = 'Perfis'
    filter_horizontal = ('planos',)
    fields = ('role', 'planos', 'empresa', 'telefone', 'bio')


@admin.register(Cliente)
class ClienteAdmin(BaseUserAdmin):
    inlines = [PerfilInline]
    list_display = ('username', 'get_full_name', 'email', 'role_info', 'is_active', 'date_joined')
    list_filter = ('is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informações Pessoais', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissões', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Datas', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'last_name', 'email', 'password1', 'password2'),
        }),
    )

    def get_full_name(self, obj):
        return obj.get_full_name() or '-'
    get_full_name.short_description = 'Nome completo'

    def role_info(self, obj):
        perfil = getattr(obj, 'perfil', None)
        if perfil:
            return perfil.get_role_display()
        return '-'
    role_info.short_description = 'Função'

    def get_default_plan_for_role(self, role):
        if role == 'admin':
            return 'Plano Premium'
        return None

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        super().save_formset(request, form, formset, change)
        if formset.model is Perfil:
            for perfil in instances:
                if perfil.pk and not perfil.planos.exists():
                    default_plan_name = self.get_default_plan_for_role(perfil.role)
                    if default_plan_name:
                        try:
                            plano = Plano.objects.get(nome__iexact=default_plan_name)
                            perfil.planos.add(plano)
                        except Plano.DoesNotExist:
                            pass


class VideoInline(admin.TabularInline):
    model = Video
    extra = 0
    fields = ('titulo', 'arquivo', 'url_externa', 'ordem', 'ativo')
    ordering = ('ordem',)


class MaterialInline(admin.TabularInline):
    model = Material
    extra = 0
    fields = ('titulo', 'arquivo', 'url_externa', 'modalidade', 'ordem', 'ativo')
    ordering = ('ordem',)


class ModuloInline(admin.TabularInline):
    model = Modulo
    extra = 0
    fields = ('titulo', 'descricao', 'ordem', 'ativo')
    ordering = ('ordem',)


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    form = CursoAdminForm
    inlines = [VideoInline, ModuloInline]
    list_display = ('titulo', 'tipo', 'ambiente', 'status', 'is_gratuito', 'is_recomendado', 'video_display', 'created_at')
    list_filter = ('tipo', 'status', 'ambiente', 'is_gratuito', 'is_recomendado')
    search_fields = ('titulo', 'descricao', 'slug')
    list_editable = ('status',)
    date_hierarchy = 'created_at'
    filter_horizontal = ('academias_extras',)
    fieldsets = (
        (None, {
            'fields': ('titulo', 'slug', 'tipo', 'descricao', 'status')
        }),
        ('Acesso', {
            'fields': ('ambiente', 'is_gratuito', 'is_recomendado', 'roles_extras', 'academias_extras'),
            'description': 'Controle de qual academy e perfis têm acesso a este curso.',
        }),
        ('Mídia', {
            'fields': ('video', 'thumbnail'),
            'description': 'Faça upload do vídeo e da thumbnail (capa) do curso.',
        }),
    )

    def video_display(self, obj):
        if obj.video:
            return '✅ Vídeo carregado'
        return '❌ Sem vídeo'
    video_display.short_description = 'Vídeo'


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    inlines = [MaterialInline]
    list_display = ('titulo', 'curso', 'ordem', 'ativo')
    list_filter = ('curso', 'ativo')
    search_fields = ('titulo', 'curso__titulo')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'modulo', 'modalidade', 'ordem', 'ativo')
    list_filter = ('modalidade', 'ativo')
    search_fields = ('titulo', 'modulo__titulo')


@admin.register(Trilha)
class TrilhaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ambiente', 'quantidade_cursos')
    list_filter = ('ambiente',)
    search_fields = ('nome', 'descricao')
    filter_horizontal = ('cursos',)

    def quantidade_cursos(self, obj):
        return obj.cursos.count()
    quantidade_cursos.short_description = 'Qtd. Cursos'

    def quantidade_cursos(self, obj):
        return obj.cursos.count()
    quantidade_cursos.short_description = 'Qtd. Cursos'


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'data', 'local')
    list_filter = ('data',)
    search_fields = ('titulo',)
    date_hierarchy = 'data'


@admin.register(Novidade)
class NovidadeAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'ativo', 'created_at')
    list_filter = ('ativo',)
    search_fields = ('titulo',)


@admin.register(LogAtividade)
class LogAtividadeAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'acao', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('usuario__username', 'acao')
    date_hierarchy = 'created_at'
    readonly_fields = ('usuario', 'acao', 'detalhes', 'created_at')


@admin.register(CursoVisualizacao)
class CursoVisualizacaoAdmin(admin.ModelAdmin):
    list_display = ('curso', 'usuario', 'visualizado_em')
    list_filter = ('visualizado_em',)
    date_hierarchy = 'visualizado_em'


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'curso', 'progresso', 'concluido', 'data_inscricao')
    list_filter = ('concluido', 'data_inscricao')
    search_fields = ('usuario__username', 'curso__titulo')


@admin.register(Ambiente)
class AmbienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo', 'created_at')
    list_filter = ('ativo',)
    search_fields = ('nome',)


@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'preco', 'ativo', 'created_at')
    list_filter = ('ativo',)
    search_fields = ('nome',)
    filter_horizontal = ('ambientes',)

    def get_default_ambientes(self, plano):
        if plano.nome.lower() == 'plano business':
            return Ambiente.objects.filter(nome__in=['Academy Contábil', 'Academy Gestão Empresarial'])
        if plano.nome.lower() == 'plano team':
            return Ambiente.objects.filter(nome__in=['Academy Orcomakers', 'Academy Team'])
        if plano.nome.lower() == 'plano premium':
            return Ambiente.objects.all()
        return Ambiente.objects.none()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        plano = form.instance
        if not plano.ambientes.exists():
            default_ambientes = self.get_default_ambientes(plano)
            if default_ambientes.exists():
                plano.ambientes.set(default_ambientes)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'role', 'empresa', 'telefone')
    list_filter = ('role',)
    search_fields = ('usuario__username', 'usuario__email', 'empresa')
    filter_horizontal = ('planos',)
    raw_id_fields = ('usuario',)


@admin.register(FormacaoAcademica)
class FormacaoAcademicaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'instituicao', 'nivel', 'area', 'inicio_ano', 'termino_ano')
    search_fields = ('usuario__username', 'instituicao', 'area')
    list_filter = ('nivel',)
    raw_id_fields = ('usuario',)


@admin.register(Habilidade)
class HabilidadeAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'nome')
    search_fields = ('usuario__username', 'nome')
    raw_id_fields = ('usuario',)


from django.contrib.admin import SimpleListFilter

class StatusAssinaturaFilter(SimpleListFilter):
    title = 'status'
    parameter_name = 'status_filtro'

    def lookups(self, request, model_admin):
        return [
            ('ativa', 'Ativo'),
            ('inativo', 'Inativo'),
            ('expirada', 'Expirado'),
            ('cancelada', 'Cancelado'),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'ativa':
            return queryset.filter(status='ativa')
        if value == 'inativo':
            return queryset.filter(status__in=['expirada', 'cancelada'])
        if value == 'expirada':
            return queryset.filter(status='expirada')
        if value == 'cancelada':
            return queryset.filter(status='cancelada')
        return queryset


@admin.register(AssinaturaPlano)
class AssinaturaPlanoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'plano', 'data_contratacao', 'data_expiracao', 'status')
    list_filter = (StatusAssinaturaFilter,)
    search_fields = ('usuario__username', 'plano__nome')
    raw_id_fields = ('usuario', 'plano')

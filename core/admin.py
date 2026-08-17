import threading

from django.contrib import admin, messages
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import redirect, get_object_or_404, render
from django.http import HttpResponseRedirect, JsonResponse
from django.utils.html import format_html
from django.urls import path, reverse
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from django import forms
from .models import Curso, Video, Modulo, Material, Trilha, Evento, EventoLeitura, Novidade, LogAtividade, Cliente, MembroOrcoma, CursoVisualizacao, Matricula, Plano, Ambiente, Perfil, Permissao, FormacaoAcademica, Habilidade, MetaSemanal, RegraAtribuicaoPlano, AcessoRoleAcademia, Comentario
from .forms import CursoAdminForm, MembroOrcomaAddForm, ClienteAddForm, ImportarUsuariosForm, TrilhaAdminForm, EMPRESA_PADRAO
from .services.importacao import processar_arquivo_excel, gerar_template_bytes, gerar_relatorio_bytes

User = get_user_model()

admin.site.site_header = 'Visão tributária Academy'
admin.site.site_title = 'Visão Tributária - Academy'
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
    verbose_name = 'Informações Corporativas'
    verbose_name_plural = 'Informações Corporativas'
    filter_horizontal = ('planos',)
    fieldsets = (
        ('Informações Corporativas', {
            'fields': ('empresa', 'unidade', 'cargo', 'cnpj', 'telefone'),
            'description': 'Preencha as informações corporativas do usuário.',
        }),
        ('Informações Adicionais', {
            'fields': ('role', 'planos', 'bio'),
        }),
    )


@admin.register(Cliente)
class ClienteAdmin(BaseUserAdmin):
    change_list_template = 'admin/core/cliente/change_list.html'

    def get_model_perms(self, request):
        return {}
    inlines = [PerfilInline]
    list_display = ('username', 'get_full_name', 'email', 'role_info', 'is_active', 'date_joined')
    list_filter = ('is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informações Pessoais', {'fields': ('first_name', 'last_name', 'email')}),
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

    def response_add(self, request, obj, post_url_continue=None):
        return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))

    def response_change(self, request, obj):
        return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))

    def response_delete(self, request, obj_display, obj_id):
        return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))

    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))


STAFF_ROLES = ('admin', 'colaborador_orcoma', 'gestor_orcoma')
CLIENT_ROLES = ('cliente_premium', 'cliente_orcoma', 'empresario', 'cliente_equipe', 'visitor')


@admin.register(MembroOrcoma)
class MembroOrcomaAdmin(BaseUserAdmin):
    change_list_template = 'admin/core/membro_orcoma/change_list.html'
    add_form_template = 'admin/core/membro_orcoma/add_form.html'
    add_form = MembroOrcomaAddForm
    inlines = [PerfilInline]
    list_display = ('username', 'get_full_name', 'email', 'role_info', 'is_active', 'date_joined')
    list_filter = ('is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informações Pessoais', {'fields': ('first_name', 'last_name', 'email')}),
        ('Datas', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        ('Dados de Acesso', {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Informações Pessoais', {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'email'),
        }),
        ('Dados Corporativos', {
            'classes': ('wide',),
            'fields': ('empresa', 'unidade', 'cargo', 'telefone'),
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

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        from django.db.models import Q

        search_query = request.GET.get('q', '').strip()

        def search_filter(qs):
            if not search_query:
                return qs
            return qs.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(username__icontains=search_query) |
                Q(perfil__empresa__icontains=search_query)
            )

        staff_users = search_filter(User.objects.filter(
            perfil__role__in=STAFF_ROLES,
            is_active=True,
        ).select_related('perfil').order_by('-date_joined'))

        client_users = search_filter(User.objects.filter(
            perfil__role__in=CLIENT_ROLES,
            is_active=True,
        ).select_related('perfil').order_by('-date_joined'))

        extra_context['staff_users'] = staff_users
        extra_context['client_users'] = client_users
        extra_context['search_query'] = search_query
        extra_context['stats'] = {
            'total_staff': staff_users.count(),
            'total_clients': client_users.count(),
            'total': staff_users.count() + client_users.count(),
        }

        return super().changelist_view(request, extra_context=extra_context)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        super().save_formset(request, form, formset, change)
        if formset.model is Perfil:
            for perfil in instances:
                if perfil.pk:
                    is_staff_role = perfil.role in STAFF_ROLES
                    user = perfil.usuario
                    needs_update = (user.is_staff != is_staff_role) or (user.is_superuser != is_staff_role)
                    if needs_update:
                        user.is_staff = is_staff_role
                        user.is_superuser = is_staff_role
                        user.save(update_fields=['is_staff', 'is_superuser'])
                    if not perfil.planos.exists():
                        default_plan_name = self.get_default_plan_for_role(perfil.role)
                        if default_plan_name:
                            try:
                                plano = Plano.objects.get(nome__iexact=default_plan_name)
                                perfil.planos.add(plano)
                            except Plano.DoesNotExist:
                                pass

    def get_default_plan_for_role(self, role):
        if role == 'admin':
            return 'Plano Premium'
        return None

    def save_model(self, request, obj, form, change):
        if not change:
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data.get('email', ''),
                password=form.cleaned_data['password1'],
            )
            user.first_name = form.cleaned_data.get('first_name', '')
            user.last_name = form.cleaned_data.get('last_name', '')
            user.is_staff = True
            user.is_superuser = True
            user.save()
            Perfil.objects.update_or_create(
                usuario=user,
                defaults={
                    'empresa': form.cleaned_data.get('empresa', EMPRESA_PADRAO),
                    'unidade': form.cleaned_data.get('unidade', ''),
                    'role': 'admin',
                    'cargo': form.cleaned_data.get('cargo', ''),
                    'telefone': form.cleaned_data.get('telefone', ''),
                },
            )
            default_plan_name = self.get_default_plan_for_role('admin')
            if default_plan_name:
                try:
                    plano = Plano.objects.get(nome__iexact=default_plan_name)
                    user.perfil.planos.add(plano)
                except Plano.DoesNotExist:
                    pass
        else:
            super().save_model(request, obj, form, change)

    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    def get_urls(self):
        custom_urls = [
            path('add_cliente/',
                 self.admin_site.admin_view(self.add_cliente_view),
                 name='core_membroorcoma_add_cliente'),
            path('<int:pk>/change_cliente/',
                 self.admin_site.admin_view(self.change_cliente_view),
                 name='core_membroorcoma_change_cliente'),
            path('<int:pk>/delete_cliente/',
                 self.admin_site.admin_view(self.delete_cliente_view),
                 name='core_membroorcoma_delete_cliente'),
            path('excluir-massa/',
                 self.admin_site.admin_view(self.excluir_massa_view),
                 name='core_membroorcoma_excluir_massa'),
            path('importar/',
                 self.admin_site.admin_view(self.importar_usuarios_view),
                 name='core_membroorcoma_importar'),
            path('importar/progresso/',
                 self.admin_site.admin_view(self.importar_progresso_api),
                 name='core_membroorcoma_importar_progresso'),
            path('importar/template/',
                 self.admin_site.admin_view(self.baixar_template_view),
                 name='core_membroorcoma_baixar_template'),
            path('importar/relatorio/',
                 self.admin_site.admin_view(self.download_relatorio_view),
                 name='core_membroorcoma_download_relatorio'),
        ]
        return custom_urls + super().get_urls()

    def add_cliente_view(self, request):
        if request.method == 'POST':
            form = ClienteAddForm(request.POST)
            if form.is_valid():
                user = form.save()
                self.message_user(request, f'Cliente "{user.get_full_name() or user.username}" criado com sucesso.')
                return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))
        else:
            form = ClienteAddForm()
        from django.contrib.admin.helpers import AdminForm
        admin_form = AdminForm(
            form,
            list(self.add_fieldsets),
            {},
            readonly_fields=[],
        )
        context = {
            **self.admin_site.each_context(request),
            'title': 'Adicionar Cliente',
            'subtitle': None,
            'adminform': admin_form,
            'add': True,
            'change': False,
            'is_popup': False,
            'opts': self.model._meta,
            'save_as': False,
            'show_save': True,
            'show_save_and_continue': False,
            'show_save_and_add_another': False,
            'add_form_template': 'admin/core/cliente/add_form.html',
        }
        return render(request, 'admin/core/cliente/add_form.html', context)

    def change_cliente_view(self, request, pk):
        user_obj = get_object_or_404(User, pk=pk)
        from django.contrib.auth.forms import UserChangeForm
        from django.contrib.admin.helpers import AdminForm

        if request.method == 'POST':
            form = UserChangeForm(request.POST, instance=user_obj)
            if form.is_valid():
                form.save()
                self.message_user(request, f'Cliente "{user_obj.get_full_name() or user_obj.username}" atualizado com sucesso.')
                return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))
        else:
            form = UserChangeForm(instance=user_obj)

        admin_form = AdminForm(
            form,
            list(self.fieldsets),
            self.get_prepopulated_fields(request),
            readonly_fields=self.get_readonly_fields(request, user_obj),
        )
        inline_instances = self.get_inline_instances(request, user_obj)
        inline_admin_formsets = []
        for inline in inline_instances:
            fieldsets = inline.get_fieldsets(request, user_obj)
            FormSet = inline.get_formset(request, user_obj)
            prefix = FormSet.get_default_prefix()
            formset = FormSet(
                instance=user_obj,
                prefix=prefix,
                queryset=inline.get_queryset(request),
            )
            inline_admin_formsets.append(
                admin.helpers.InlineAdminFormSet(
                    inline,
                    formset,
                    fieldsets,
                    model_admin=self,
                    has_add_permission=inline.has_add_permission(request, user_obj),
                    has_change_permission=inline.has_change_permission(request, user_obj),
                    has_delete_permission=inline.has_delete_permission(request, user_obj),
                    has_view_permission=inline.has_view_permission(request, user_obj),
                )
            )
        context = {
            **self.admin_site.each_context(request),
            'title': f'Editar Cliente: {user_obj.get_full_name() or user_obj.username}',
            'subtitle': None,
            'form': form,
            'adminform': admin_form,
            'object_id': pk,
            'original': user_obj,
            'is_popup': False,
            'inline_admin_formsets': inline_admin_formsets,
            'errors': admin.helpers.AdminErrorList(form, []),
            'opts': self.model._meta,
            'add': False,
            'change': True,
            'save_as': False,
            'show_save': True,
            'show_save_and_continue': False,
            'show_save_and_add_another': False,
            'has_view_permission': True,
            'has_change_permission': True,
            'has_add_permission': False,
            'has_delete_permission': True,
        }
        return render(request, 'admin/core/cliente/change_form.html', context)

    def delete_cliente_view(self, request, pk):
        from django.db import transaction
        from core.models import (
            Matricula, Certificado, FormacaoAcademica, Habilidade,
            MetaSemanal, LogAtividade, Notificacao, CursoVisualizacao,
            Avaliacao, Perfil
        )
        
        user_obj = get_object_or_404(User, pk=pk)
        
        if request.method == 'POST':
            try:
                with transaction.atomic():
                    # Deleta todos os registros relacionados manualmente para evitar erros de FK
                    matriculas = Matricula.objects.filter(usuario=user_obj)
                    for matricula in matriculas:
                        # Deleta certificados primeiro (dependem de matrícula)
                        Certificado.objects.filter(matricula=matricula).delete()
                    
                    # Deleta todos os outros relacionamentos
                    Matricula.objects.filter(usuario=user_obj).delete()
                    FormacaoAcademica.objects.filter(usuario=user_obj).delete()
                    Habilidade.objects.filter(usuario=user_obj).delete()
                    MetaSemanal.objects.filter(usuario=user_obj).delete()
                    LogAtividade.objects.filter(usuario=user_obj).delete()
                    Notificacao.objects.filter(usuario=user_obj).delete()
                    CursoVisualizacao.objects.filter(usuario=user_obj).delete()
                    Avaliacao.objects.filter(usuario=user_obj).delete()
                    Perfil.objects.filter(usuario=user_obj).delete()
                    
                    # Finalmente deleta o usuário
                    username = user_obj.get_full_name() or user_obj.username
                    user_obj.delete()
                    
                    self.message_user(
                        request, 
                        f'Cliente "{username}" excluído com sucesso.',
                        messages.SUCCESS
                    )
                    return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))
            except Exception as e:
                self.message_user(
                    request, 
                    f'Erro ao excluir cliente: {str(e)}',
                    messages.ERROR
                )
                return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))
        
        # Conta registros relacionados para mostrar no template
        context = {
            **self.admin_site.each_context(request),
            'title': f'Excluir Cliente: {user_obj.get_full_name() or user_obj.username}',
            'object': user_obj,
            'object_name': user_obj.get_full_name() or user_obj.username,
            'is_popup': False,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        }
        return render(request, 'admin/core/cliente/delete_confirm.html', context)

    def importar_usuarios_view(self, request):
        try:
            if request.method == 'POST':
                form = ImportarUsuariosForm(request.POST, request.FILES)
                if form.is_valid():
                    arquivo = request.FILES['arquivo']
                    arquivo.seek(0)

                    from core.services.importacao import processar_arquivo_excel
                    resultado, erro = processar_arquivo_excel(arquivo, criar_usuarios=True)

                    if erro:
                        for campo, msg in erro.items():
                            self.message_user(request, msg, level=messages.ERROR)
                        return HttpResponseRedirect(reverse('admin:core_membroorcoma_importar'))

                    s = resultado['sucessos']
                    e = resultado['total_erros']
                    if s:
                        self.message_user(
                            request,
                            f'{s} cliente(s) cadastrado(s) com sucesso.'
                            + (f' {e} erro(s) ignorado(s).' if e else ''),
                            level=messages.SUCCESS if e == 0 else messages.WARNING,
                        )
                    else:
                        self.message_user(
                            request,
                            'Nenhum cliente foi cadastrado. Verifique se os dados estão corretos.',
                            level=messages.WARNING,
                        )

                    if resultado['erros']:
                        for err in resultado['erros'][:20]:
                            self.message_user(
                                request,
                                f"Linha {err.get('linha','?')}: {err.get('username','?')} - {err.get('motivo','')}",
                                level=messages.WARNING,
                            )
                        if len(resultado['erros']) > 20:
                            self.message_user(request, f"... e mais {len(resultado['erros'])-20} erro(s).", messages.WARNING)

                    return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))
            else:
                form = ImportarUsuariosForm()

            return render(request, 'admin/core/membro_orcoma/importar_usuarios.html', {
                **self.admin_site.each_context(request),
                'title': 'Importar Usuários',
                'form': form,
                'opts': self.model._meta,
            })
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.message_user(
                request,
                f'Erro ao processar importação: {str(e)}',
                level=messages.ERROR
            )
            print(f"ERRO NA IMPORTAÇÃO: {error_detail}")

            form = ImportarUsuariosForm()
            return render(request, 'admin/core/membro_orcoma/importar_usuarios.html', {
                **self.admin_site.each_context(request),
                'title': 'Importar Usuários',
                'form': form,
                'opts': self.model._meta,
                'error_detail': str(e),
            })

    def baixar_template_view(self, request):
        from django.http import HttpResponse

        output = gerar_template_bytes()
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="template_usuarios_massa.xlsx"'
        return response

    def download_relatorio_view(self, request):
        from django.http import HttpResponse

        dados = request.session.pop('relatorio_importacao', None)
        if not dados:
            self.message_user(request, 'Nenhum relatório disponível.', level=messages.WARNING)
            return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))

        output = gerar_relatorio_bytes(dados)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="relatorio_usuarios_cadastrados.xlsx"'
        return response

    def importar_progresso_api(self, request):
        """API endpoint para retornar o progresso da importação em tempo real"""
        from django.http import JsonResponse
        from core.services.progresso_importacao import obter_progresso
        
        import_id = request.GET.get('import_id')
        if not import_id:
            return JsonResponse({'status': 'error', 'message': 'import_id não fornecido'})
        
        dados = obter_progresso(import_id)
        if not dados:
            return JsonResponse({'status': 'error', 'message': 'Importação não encontrada'})
        
        return JsonResponse(dados)

    def excluir_massa_view(self, request):
        from django.db import transaction
        from django.http import HttpResponseRedirect
        from core.models import (
            Matricula, Certificado, FormacaoAcademica, Habilidade,
            MetaSemanal, LogAtividade, Notificacao, CursoVisualizacao,
            Avaliacao, Perfil
        )
        
        if request.method == 'POST':
            usuarios_ids = request.POST.getlist('usuarios_ids')
            
            if not usuarios_ids:
                self.message_user(request, 'Nenhum usuário selecionado.', level=messages.WARNING)
                return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))
            
            try:
                with transaction.atomic():
                    usuarios = User.objects.filter(pk__in=usuarios_ids)
                    total_excluidos = usuarios.count()
                    
                    # Coleta todos os IDs de usuários para filtrar
                    usuarios_ids_list = list(usuarios.values_list('id', flat=True))
                    
                    # Deleta em lote, na ordem correta, para evitar erros de FK
                    # 1. Certificados (dependem de matrículas)
                    matriculas_ids = Matricula.objects.filter(usuario_id__in=usuarios_ids_list).values_list('id', flat=True)
                    Certificado.objects.filter(matricula_id__in=matriculas_ids).delete()
                    
                    # 2. Demais registros relacionados (todos de uma vez)
                    Matricula.objects.filter(usuario_id__in=usuarios_ids_list).delete()
                    FormacaoAcademica.objects.filter(usuario_id__in=usuarios_ids_list).delete()
                    Habilidade.objects.filter(usuario_id__in=usuarios_ids_list).delete()
                    MetaSemanal.objects.filter(usuario_id__in=usuarios_ids_list).delete()
                    LogAtividade.objects.filter(usuario_id__in=usuarios_ids_list).delete()
                    Notificacao.objects.filter(usuario_id__in=usuarios_ids_list).delete()
                    CursoVisualizacao.objects.filter(usuario_id__in=usuarios_ids_list).delete()
                    Avaliacao.objects.filter(usuario_id__in=usuarios_ids_list).delete()
                    Perfil.objects.filter(usuario_id__in=usuarios_ids_list).delete()
                    
                    # 3. Finalmente deleta os usuários
                    usuarios.delete()
                    
                    self.message_user(
                        request,
                        f'{total_excluidos} usuário(s) excluído(s) com sucesso.',
                        messages.SUCCESS
                    )
                    return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))
                    
            except Exception as e:
                self.message_user(
                    request,
                    f'Erro ao excluir usuários: {str(e)}',
                    messages.ERROR
                )
                return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))
        
        # GET request - mostra a página de confirmação
        usuarios_ids = request.GET.getlist('usuarios_ids')
        
        if not usuarios_ids:
            self.message_user(request, 'Nenhum usuário selecionado.', level=messages.WARNING)
            return HttpResponseRedirect(reverse('admin:core_membroorcoma_changelist'))
        
        usuarios = User.objects.filter(pk__in=usuarios_ids).select_related('perfil')
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Excluir Clientes em Massa',
            'usuarios': usuarios,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        }
        return render(request, 'admin/core/membro_orcoma/excluir_massa.html', context)


class VideoInline(admin.StackedInline):
    model = Video
    extra = 0
    can_delete = True
    fields = ('modulo', 'titulo', 'arquivo', 'url_externa', 'ordem', 'ativo')
    ordering = ('ordem',)


class MaterialInline(admin.TabularInline):
    model = Material
    extra = 0
    fields = ('titulo', 'arquivo', 'url_externa', 'modalidade', 'ordem', 'ativo')
    ordering = ('ordem',)


class ModuloInline(admin.StackedInline):
    model = Modulo
    extra = 0
    can_delete = True
    fields = ('titulo', 'descricao', 'ordem', 'ativo')
    ordering = ('ordem',)


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    form = CursoAdminForm
    inlines = [VideoInline, ModuloInline]
    change_list_template = 'admin/core/curso/change_list.html'
    list_display = ('titulo', 'tipo', 'ambiente', 'status', 'is_gratuito', 'is_recomendado', 'video_display', 'created_at')
    list_filter = ('ambiente',)
    search_fields = ('titulo', 'descricao', 'slug')
    list_editable = ('status',)
    date_hierarchy = 'created_at'
    fieldsets = (
        (None, {
            'fields': ('titulo', 'slug', 'tipo', 'descricao', 'status')
        }),
        ('Acesso', {
            'fields': ('ambiente', 'is_gratuito', 'is_recomendado', 'roles_extras'),
            'description': 'Controle de qual academy e perfis têm acesso a este curso.',
        }),
        ('Mídia', {
            'fields': ('thumbnail',),
            'description': 'Faça upload da thumbnail (capa) do curso.',
        }),
    )

    class Media:
        css = {
            'all': ('admin/css/curso_admin.css',)
        }

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/toggle-gratuito/',
                self.admin_site.admin_view(self.toggle_gratuito),
                name='core_curso_toggle_gratuito',
            ),
            path(
                '<path:object_id>/toggle-recomendado/',
                self.admin_site.admin_view(self.toggle_recomendado),
                name='core_curso_toggle_recomendado',
            ),
            path(
                '<path:object_id>/toggle-status/',
                self.admin_site.admin_view(self.toggle_status),
                name='core_curso_toggle_status',
            ),
        ]
        return custom_urls + urls

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('ambiente')

    def video_display(self, obj):
        if obj.video:
            return '✅ Vídeo carregado'
        return '❌ Sem vídeo'
    video_display.short_description = 'Vídeo'

    # ── Toggles rápidos (Gratuito / Recomendado / Status) ──
    def _toggle_boolean(self, request, object_id, field_name):
        if request.method != 'POST':
            return JsonResponse({'ok': False, 'error': 'Método não permitido.'}, status=405)
        curso = get_object_or_404(Curso, pk=object_id)
        value = request.POST.get('value') == 'true'
        setattr(curso, field_name, value)
        curso.save(update_fields=[field_name])
        return JsonResponse({'ok': True, 'value': value})

    def toggle_gratuito(self, request, object_id):
        return self._toggle_boolean(request, object_id, 'is_gratuito')

    def toggle_recomendado(self, request, object_id):
        return self._toggle_boolean(request, object_id, 'is_recomendado')

    def toggle_status(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'ok': False, 'error': 'Método não permitido.'}, status=405)
        curso = get_object_or_404(Curso, pk=object_id)
        publicado = request.POST.get('value') == 'true'
        curso.status = 'publicado' if publicado else 'rascunho'
        curso.save(update_fields=['status'])
        return JsonResponse({'ok': True, 'status': curso.status})


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
    change_list_template = 'admin/core/trilha/change_list.html'
    change_form_template = 'admin/core/trilha/change_form.html'
    form = TrilhaAdminForm
    list_display = ('nome', 'ambiente', 'quantidade_cursos')
    list_filter = ('ambiente',)
    search_fields = ('nome', 'descricao')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('ambiente').prefetch_related('cursos')

    def quantidade_cursos(self, obj):
        return obj.cursos.count()
    quantidade_cursos.short_description = 'Qtd. Cursos'

    def quantidade_cursos(self, obj):
        return obj.cursos.count()
    quantidade_cursos.short_description = 'Qtd. Cursos'


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    change_list_template = 'admin/core/evento/change_list.html'
    list_display = ('titulo', 'data', 'local')
    list_filter = ('data',)
    search_fields = ('titulo',)
    date_hierarchy = 'data'
    fields = ('titulo', 'descricao', 'imagem', 'data', 'local', 'capacidade', 'url')


@admin.register(EventoLeitura)
class EventoLeituraAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'evento', 'lida_em')
    list_filter = ('lida_em',)
    search_fields = ('usuario__username', 'usuario__email', 'evento__titulo')


@admin.register(Novidade)
class NovidadeAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'ativo', 'created_at')
    list_filter = ('ativo',)
    search_fields = ('titulo',)

    def get_model_perms(self, request):
        return {}


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
    change_list_template = 'admin/core/ambiente/change_list.html'
    list_display = ('capa_thumb', 'nome', 'descricao_curta', 'ativo', 'created_at')
    list_display_links = ('nome',)
    list_filter = ('ativo',)
    search_fields = ('nome',)
    fieldsets = (
        (None, {
            'fields': ('nome', 'descricao', 'imagem', 'plano', 'ativo'),
        }),
    )

    @admin.display(description='Capa')
    def capa_thumb(self, obj):
        if obj.imagem:
            return format_html(
                '<img src="{}" style="width:72px;height:40px;object-fit:cover;border-radius:6px;display:block" />',
                obj.imagem.url,
            )
        return format_html('<span style="color:#64748b">Sem imagem</span>')

    @admin.display(description='Descrição')
    def descricao_curta(self, obj):
        return obj.descricao[:80] if obj.descricao else '—'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/toggle-ativo/',
                self.admin_site.admin_view(self.toggle_ativo),
                name='core_ambiente_toggle_ativo',
            ),
        ]
        return custom_urls + urls

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('plano')

    def toggle_ativo(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'ok': False, 'error': 'Método não permitido.'}, status=405)
        ambiente = get_object_or_404(Ambiente, pk=object_id)
        value = request.POST.get('value') == 'true'
        ambiente.ativo = value
        ambiente.save(update_fields=['ativo'])
        return JsonResponse({'ok': True, 'value': value})


@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'preco', 'ativo', 'created_at')
    list_filter = ('ativo',)

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


@admin.register(MetaSemanal)
class MetaSemanalAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'titulo', 'meta_horas', 'horas_concluidas', 'percentual', 'semana_inicio')
    list_filter = ('concluida', 'semana_inicio')
    search_fields = ('usuario__username', 'titulo')
    readonly_fields = ('percentual',)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'role', 'empresa', 'telefone')
    list_filter = ('role',)
    search_fields = ('usuario__username', 'usuario__email', 'empresa')
    filter_horizontal = ('planos',)
    raw_id_fields = ('usuario',)


@admin.register(AcessoRoleAcademia)
class AcessoRoleAcademiaAdmin(admin.ModelAdmin):
    list_display = ('role', 'academia', 'ativo')
    list_filter = ('role', 'ativo', 'academia')
    search_fields = ('role', 'academia__nome')
    list_editable = ('ativo',)
    ordering = ('role', 'academia__nome')


@admin.register(RegraAtribuicaoPlano)
class RegraAtribuicaoPlanoAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'cnpj', 'plano', 'ativo')
    list_filter = ('ativo', 'plano')
    search_fields = ('empresa', 'cnpj')


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


@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'modulo', 'texto_resumido', 'created_at')
    search_fields = ('usuario__username', 'texto', 'modulo__titulo')
    list_filter = ('created_at',)
    raw_id_fields = ('usuario', 'modulo', 'comentario_pai')

    @admin.display(description='Comentário')
    def texto_resumido(self, obj):
        return obj.texto[:50]




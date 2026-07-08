from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Curso, Trilha, Evento, Novidade, LogAtividade, Cliente, CursoVisualizacao, Matricula, Plano, Ambiente, Perfil

admin.site.site_header = 'Orcoma Academy'
admin.site.site_title = 'Orcoma Academy - Admin'
admin.site.index_title = 'Painel Administrativo'
admin.site.site_url = None

admin.site.unregister(User)
admin.site.unregister(Group)


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


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'status', 'created_at')
    list_filter = ('tipo', 'status')
    search_fields = ('titulo', 'descricao')
    list_editable = ('status',)
    date_hierarchy = 'created_at'


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


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'role', 'empresa', 'telefone')
    list_filter = ('role',)
    search_fields = ('usuario__username', 'usuario__email', 'empresa')
    filter_horizontal = ('planos',)
    raw_id_fields = ('usuario',)

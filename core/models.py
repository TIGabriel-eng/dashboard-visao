from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.validators import validate_video_file


class Cliente(User):
    class Meta:
        proxy = True
        verbose_name = 'Usuário/Cliente'
        verbose_name_plural = 'Usuários/Clientes'

    def __str__(self):
        return f'{self.get_full_name() or self.username}'


class Permissao(Group):
    class Meta:
        proxy = True
        verbose_name = 'Permissão'
        verbose_name_plural = 'Permissões'


class Ambiente(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name='Academy')
    descricao = models.TextField(blank=True)
    plano = models.ForeignKey(
        'Plano',
        on_delete=models.PROTECT,
        related_name='academias',
        null=True,
        blank=True,
        verbose_name='Plano',
    )
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Academy'
        verbose_name_plural = 'Academies'
        ordering = ['nome']
        permissions = [
            ('gerenciar_ambientes', 'Pode gerenciar academies'),
        ]

    def __str__(self):
        return self.nome


class Plano(models.Model):
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ambientes = models.ManyToManyField(Ambiente, related_name='planos', blank=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Plano'
        verbose_name_plural = 'Planos'
        ordering = ['nome']
        permissions = [
            ('gerenciar_planos', 'Pode gerenciar planos'),
        ]

    def __str__(self):
        return self.nome


class AcessoRoleAcademia(models.Model):
    role = models.CharField(max_length=30, verbose_name='Perfil')
    academia = models.ForeignKey(
        Ambiente,
        on_delete=models.CASCADE,
        related_name='acessos_role',
        verbose_name='Academy',
    )
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Acesso perfil × academy'
        verbose_name_plural = 'Acessos perfil × academy'
        unique_together = [('role', 'academia')]
        indexes = [
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f'{self.role} → {self.academia.nome}'


class Curso(models.Model):
    TIPO_CHOICES = [
        ('curso', 'Curso'),
        ('video', 'Vídeo'),
    ]
    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('publicado', 'Publicado'),
        ('arquivado', 'Arquivado'),
    ]

    titulo = models.CharField(max_length=255)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='curso')
    descricao = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='rascunho')
    ambiente = models.ForeignKey(
        Ambiente,
        on_delete=models.PROTECT,
        related_name='cursos',
        null=True,
        blank=True,
        verbose_name='Academy',
        help_text='Define em qual academy o curso aparece no site.',
    )
    is_gratuito = models.BooleanField(
        default=False,
        verbose_name='Gratuito',
        help_text='Visível e acessível por todos os perfis, incluindo visitantes.',
    )
    roles_extras = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Perfis extras',
        help_text='Perfis adicionais com acesso a este curso (ex.: ["empresario"]).',
    )
    academias_extras = models.ManyToManyField(
        Ambiente,
        related_name='cursos_extras',
        blank=True,
        verbose_name='Academies extras',
        help_text='Academies adicionais com acesso pontual a este curso.',
    )
    video = models.FileField(
        upload_to='cursos/videos/',
        blank=True,
        null=True,
        verbose_name='Vídeo (legado)',
        validators=[validate_video_file],
        help_text='Campo legado. Prefira cadastrar aulas no inline "Vídeos".',
    )
    thumbnail = models.ImageField(upload_to='cursos/thumbnails/', blank=True, null=True, verbose_name='Thumbnail/Capa')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ambiente']),
            models.Index(fields=['is_gratuito']),
            models.Index(fields=['status']),
        ]
        permissions = [
            ('cadastrar_videos', 'Pode cadastrar vídeos'),
            ('editar_videos', 'Pode editar vídeos'),
            ('excluir_videos', 'Pode excluir vídeos'),
            ('publicar_cursos', 'Pode publicar cursos'),
        ]

    def __str__(self):
        return self.titulo

    def user_can_access(self, user):
        from core.services.acesso import user_can_access_curso
        return user_can_access_curso(self, user)


class Video(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='videos')
    titulo = models.CharField(max_length=255)
    arquivo = models.FileField(
        upload_to='cursos/videos/',
        blank=True,
        null=True,
        validators=[validate_video_file],
        verbose_name='Arquivo de vídeo',
    )
    url_externa = models.URLField(
        blank=True,
        verbose_name='URL externa',
        help_text='YouTube, Vimeo ou outro link. Use quando não houver upload.',
    )
    ordem = models.PositiveIntegerField(default=0, verbose_name='Ordem')
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Vídeo'
        verbose_name_plural = 'Vídeos'
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.curso.titulo} — {self.titulo}'


class Trilha(models.Model):
    nome = models.CharField(max_length=255)
    ambiente = models.ForeignKey(Ambiente, on_delete=models.PROTECT, verbose_name='Academy')
    descricao = models.TextField(blank=True)
    cursos = models.ManyToManyField(Curso, related_name='trilhas', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Trilha'
        verbose_name_plural = 'Trilhas'
        permissions = [
            ('gerenciar_trilhas', 'Pode gerenciar trilhas'),
        ]

    def __str__(self):
        return self.nome


class Evento(models.Model):
    titulo = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    data = models.DateTimeField()
    local = models.CharField(max_length=255, blank=True)
    capacidade = models.PositiveIntegerField(default=0, help_text='0 = sem limite')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'
        ordering = ['data']
        permissions = [
            ('gerenciar_eventos', 'Pode gerenciar eventos'),
        ]

    def __str__(self):
        return self.titulo


class CursoVisualizacao(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='visualizacoes')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='visualizacoes')
    visualizado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Visualização de Curso'
        verbose_name_plural = 'Visualizações de Cursos'
        ordering = ['-visualizado_em']


class Matricula(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='matriculas')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='matriculas')
    data_inscricao = models.DateTimeField(auto_now_add=True)
    progresso = models.PositiveIntegerField(default=0, help_text='Percentual 0-100')
    concluido = models.BooleanField(default=False)
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Matrícula'
        verbose_name_plural = 'Matrículas'
        ordering = ['-data_inscricao']
        unique_together = ['usuario', 'curso']

    def __str__(self):
        return f'{self.usuario} - {self.curso}'


class Novidade(models.Model):
    titulo = models.CharField(max_length=255)
    conteudo = models.TextField()
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Novidade'
        verbose_name_plural = 'Novidades'
        ordering = ['-created_at']
        permissions = [
            ('gerenciar_novidades', 'Pode gerenciar novidades'),
        ]

    def __str__(self):
        return self.titulo


class LogAtividade(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='logs')
    acao = models.CharField(max_length=255)
    detalhes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log de Atividade'
        verbose_name_plural = 'Logs de Atividades'
        ordering = ['-created_at']
        permissions = [
            ('ver_logs_atividade', 'Pode ver logs de atividade'),
        ]

    def __str__(self):
        return f'{self.usuario} - {self.acao}'


class Perfil(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('cliente_premium', 'Cliente Premium'),
        ('cliente_orcoma', 'Cliente Orcoma'),
        ('empresario', 'Empresário Não Cliente'),
        ('cliente_equipe', 'Cliente Equipe'),
        ('colaborador_orcoma', 'Colaborador Orcoma'),
        ('gestor_orcoma', 'Gestor Orcoma (interno)'),
        ('visitor', 'Visitante'),
    ]

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='cliente_orcoma', db_index=True)
    planos = models.ManyToManyField(Plano, blank=True, related_name='perfis')
    empresa = models.CharField(max_length=200, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfis'
        permissions = [
            ('gerenciar_clientes', 'Pode gerenciar clientes'),
            ('remover_clientes', 'Pode remover clientes'),
            ('gerenciar_permissoes', 'Pode gerenciar permissões'),
        ]

    def __str__(self):
        return f'{self.usuario.get_full_name() or self.usuario.username} - {self.get_role_display()}'


class FormacaoAcademica(models.Model):
    NIVEL_CHOICES = [
        ('tecnico', 'Técnico'),
        ('tecnologo', 'Tecnólogo'),
        ('bacharel', 'Bacharel'),
        ('posgraduado', 'Pós-graduado'),
        ('mestre', 'Mestre'),
        ('doutor', 'Doutor'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='formacoes')
    instituicao = models.CharField(max_length=255)
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES)
    area = models.CharField(max_length=255)
    inicio_mes = models.CharField(max_length=20)
    inicio_ano = models.CharField(max_length=4)
    termino_mes = models.CharField(max_length=20, blank=True)
    termino_ano = models.CharField(max_length=4, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Formação Acadêmica'
        verbose_name_plural = 'Formações Acadêmicas'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.area} - {self.instituicao}'


class Habilidade(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='habilidades')
    nome = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Habilidade'
        verbose_name_plural = 'Habilidades'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class AssinaturaPlano(models.Model):
    STATUS_CHOICES = [
        ('ativa', 'Ativo'),
        ('inativo', 'Inativo'),
        ('expirada', 'Expirado'),
        ('cancelada', 'Cancelado'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assinaturas')
    plano = models.ForeignKey(Plano, on_delete=models.CASCADE, related_name='assinaturas')
    data_contratacao = models.DateField()
    data_expiracao = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativa')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Assinatura de Plano'
        verbose_name_plural = 'Assinaturas de Planos'
        ordering = ['-data_contratacao']

    def __str__(self):
        labels = dict(self.STATUS_CHOICES)
        return f'{self.usuario.username} - {self.plano.nome} ({labels.get(self.status, self.status)})'


@receiver(post_save, sender=User)
def criar_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)

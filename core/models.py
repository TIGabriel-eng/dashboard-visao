from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from core.validators import validate_video_file


class Cliente(User):
    class Meta:
        proxy = True
        verbose_name = 'Usuário/Cliente'
        verbose_name_plural = 'Usuários/Clientes'

    def __str__(self):
        return f'{self.get_full_name() or self.username}'


class MembroOrcoma(User):
    class Meta:
        proxy = True
        verbose_name = 'Membro Orcoma'
        verbose_name_plural = 'Membros Orcoma'

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
    slug = models.SlugField(max_length=255, unique=True, blank=True, help_text='Identificador único no URL (ex: reforma-tributaria)')
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
    is_recomendado = models.BooleanField(
        default=False,
        verbose_name='Recomendado',
        help_text='Aparece na seção "Recomendado para você" nas academies.',
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

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.titulo)
            slug = base_slug
            counter = 1
            while Curso.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def user_can_access(self, user):
        from core.services.acesso import user_can_access_curso
        return user_can_access_curso(self, user)


class Video(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='videos')
    modulo = models.ForeignKey(
        'Modulo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='videos', verbose_name='Módulo',
    )
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


class Modulo(models.Model):
    """Módulo de um curso - agrupa vídeos e materiais relacionados"""
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='modulos')
    titulo = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    ordem = models.PositiveIntegerField(default=0, verbose_name='Ordem')
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Módulo'
        verbose_name_plural = 'Módulos'
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.curso.titulo} — {self.titulo}'


class Material(models.Model):
    """Materiais de apoio (PDFs, XLS, ZIP) vinculados a módulos"""
    MODALIDADE_CHOICES = [
        ('pdf', 'PDF'),
        ('xls', 'Excel'),
        ('xlsx', 'Excel (XLSX)'),
        ('zip', 'ZIP'),
        ('link', 'Link Externo'),
    ]
    
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='materiais')
    titulo = models.CharField(max_length=255)
    arquivo = models.FileField(
        upload_to='cursos/materiais/',
        blank=True,
        null=True,
        verbose_name='Arquivo',
    )
    url_externa = models.URLField(
        blank=True,
        verbose_name='URL externa',
        help_text='Use quando o arquivo estiver hospedado em outro lugar.',
    )
    modalidade = models.CharField(max_length=10, choices=MODALIDADE_CHOICES, default='pdf')
    ordem = models.PositiveIntegerField(default=0, verbose_name='Ordem')
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Material'
        verbose_name_plural = 'Materiais'
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.modulo.curso.titulo} — {self.titulo}'


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
    imagem = models.ImageField(upload_to='eventos/', blank=True, null=True, verbose_name='Imagem')
    data = models.DateTimeField()
    local = models.CharField(max_length=255, blank=True)
    capacidade = models.PositiveIntegerField(default=0, help_text='0 = sem limite')
    url = models.URLField(blank=True, verbose_name='Link externo')
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
    ultimo_segundo_assistido = models.PositiveIntegerField(default=0, help_text='Último segundo do vídeo assistido')
    tempo_total_assistido = models.FloatField(default=0, help_text='Tempo total acumulado assistido em segundos')
    video_corrente = models.ForeignKey(
        'Video',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matriculas_ultimo_video',
        help_text='Último vídeo acessado pelo aluno neste curso'
    )

    class Meta:
        verbose_name = 'Matrícula'
        verbose_name_plural = 'Matrículas'
        ordering = ['-data_inscricao']
        unique_together = ['usuario', 'curso']

    def __str__(self):
        return f'{self.usuario} - {self.curso}'


class Certificado(models.Model):
    matricula = models.OneToOneField(Matricula, on_delete=models.CASCADE, related_name='certificado')
    codigo = models.CharField(max_length=30, unique=True, help_text='Código único de validação do certificado')
    emitido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Certificado'
        verbose_name_plural = 'Certificados'
        ordering = ['-emitido_em']

    def __str__(self):
        return f'Certificado {self.codigo} - {self.matricula.curso.titulo}'

    def save(self, *args, **kwargs):
        if not self.codigo:
            import uuid
            self.codigo = 'ORC-' + uuid.uuid4().hex[:8].upper()
        super().save(*args, **kwargs)


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


class Notificacao(models.Model):
    TIPO_CHOICES = [
        ('boas_vindas', 'Boas-vindas'),
        ('curso_concluido', 'Curso Concluído'),
        ('evento', 'Evento'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificacoes')
    titulo = models.CharField(max_length=255)
    mensagem = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    lida = models.BooleanField(default=False)
    link = models.CharField(max_length=200, blank=True, help_text='URL opcional para ação relacionada')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['usuario', 'lida', '-created_at']),
        ]

    def __str__(self):
        return f'{self.titulo} - {self.usuario.username}'


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

    REGIME_FEDERAL_CHOICES = [
        ('', '---------'),
        ('mei', 'MEI'),
        ('me', 'ME'),
        ('epp', 'EPP'),
    ]

    UNIDADE_CHOICES = [
        ('', '---------'),
        ('maracas', 'Maracás'),
        ('salvador', 'Salvador'),
        ('aguacara', 'Jaguaquara'),
        ('jequie_1', 'Jiquié 1'),
        ('jequie_2', 'Jequié 2'),
        ('seabra', 'Seabra'),
        ('itaberaba_publica', 'Itaberaba (Orcoma Pública)'),
        ('itaberaba', 'Itaberaba'),
        ('feira_de_santana', 'Feira de Santana'),
        ('jiquirica', 'Jiquiriça'),
        ('ruy_barbosa', 'Ruy Barbosa'),
        ('sao_paulo', 'São Paulo'),
        ('utinga', 'Utinga'),
        ('varzea_nova', 'Várzea Nova'),
    ]

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='cliente_orcoma', db_index=True)
    planos = models.ManyToManyField(Plano, blank=True, related_name='perfis')
    empresa = models.CharField(max_length=200, blank=True, verbose_name='Empresa')
    unidade = models.CharField(max_length=30, choices=UNIDADE_CHOICES, blank=True, verbose_name='Unidade')
    is_empresario = models.BooleanField(default=False, verbose_name='É Empresário?')
    cnpj = models.CharField(max_length=18, blank=True, verbose_name='CNPJ da Empresa')
    regime_federal = models.CharField(max_length=10, choices=REGIME_FEDERAL_CHOICES, blank=True, verbose_name='Regime Federal')
    telefone = models.CharField(max_length=20, blank=True, verbose_name='Telefone Corporativo')
    cargo = models.CharField(max_length=200, blank=True, verbose_name='Cargo')
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name='Avatar')
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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


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


class RegraAtribuicaoPlano(models.Model):
    cnpj = models.CharField(max_length=18, unique=True)
    empresa = models.CharField(max_length=200)
    plano = models.ForeignKey(Plano, on_delete=models.PROTECT, related_name='regras_atribuicao')
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Regra de Atribuição de Plano'
        verbose_name_plural = 'Regras de Atribuição de Planos'
        ordering = ['empresa']

    def __str__(self):
        return f'{self.empresa} → {self.plano.nome}'


class MetaSemanal(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='metas_semanais')
    titulo = models.CharField(max_length=255)
    meta_horas = models.PositiveIntegerField(default=5, help_text='Meta de horas semanais')
    horas_concluidas = models.FloatField(default=0)
    semana_inicio = models.DateField(help_text='Início da semana')
    semana_fim = models.DateField(help_text='Fim da semana')
    concluida = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    baseline_tempo = models.FloatField(default=0, help_text='Tempo total acumulado (em segundos) no momento da criação da meta')

    class Meta:
        verbose_name = 'Meta Semanal'
        verbose_name_plural = 'Metas Semanais'
        ordering = ['-semana_inicio']

    def __str__(self):
        return f'{self.usuario.username} - {self.titulo}'

    @property
    def percentual(self):
        if self.meta_horas <= 0:
            return 0
        return min(round((self.horas_concluidas / self.meta_horas) * 100), 100)


class Avaliacao(models.Model):
    """Avaliações e comentários de usuários sobre módulos"""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='avaliacoes')
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='avaliacoes')
    nota = models.PositiveIntegerField(choices=[(i, f'{i} estrelas') for i in range(1, 6)])
    comentario = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Avaliação'
        verbose_name_plural = 'Avaliações'
        ordering = ['-created_at']
        unique_together = ['usuario', 'modulo']

    def __str__(self):
        return f'{self.usuario.username} - {self.modulo.titulo} - {self.nota}★'


@receiver(post_save, sender=User)
def criar_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)


@receiver(post_save, sender=Perfil)
def atribuir_plano_por_cnpj(sender, instance, **kwargs):
    if instance.cnpj:
        regra = RegraAtribuicaoPlano.objects.filter(cnpj=instance.cnpj, ativo=True).first()
        if regra:
            instance.planos.add(regra.plano)

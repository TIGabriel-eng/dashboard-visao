from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Cliente(User):
    class Meta:
        proxy = True
        verbose_name = 'Usuário/Cliente'
        verbose_name_plural = 'Usuários/Clientes'

    def __str__(self):
        return f'{self.get_full_name() or self.username}'


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'
        ordering = ['-created_at']

    def __str__(self):
        return self.titulo


class Trilha(models.Model):
    nome = models.CharField(max_length=255)
    ambiente = models.ForeignKey('Ambiente', on_delete=models.PROTECT, verbose_name='Ambiente')
    descricao = models.TextField(blank=True)
    cursos = models.ManyToManyField(Curso, related_name='trilhas', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Trilha'
        verbose_name_plural = 'Trilhas'

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

    def __str__(self):
        return f'{self.usuario} - {self.acao}'


class Ambiente(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ambiente'
        verbose_name_plural = 'Ambientes'
        ordering = ['nome']

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

    def __str__(self):
        return self.nome


class Perfil(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('cliente_orcoma', 'Cliente Orcoma'),
        ('colaborador_orcoma', 'Orcoma Team'),
        ('gestor_orcoma', 'Orcoma Business'),
        ('empresario', 'Empresário'),
        ('visitor', 'Visitante'),
    ]

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='cliente_orcoma')
    planos = models.ManyToManyField(Plano, blank=True, related_name='perfis')
    empresa = models.CharField(max_length=200, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfis'

    def __str__(self):
        return f'{self.usuario.get_full_name() or self.usuario.username} - {self.get_role_display()}'


@receiver(post_save, sender=User)
def criar_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)

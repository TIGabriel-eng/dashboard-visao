import re

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import (
    Curso, Trilha, Evento, Novidade, LogAtividade, Perfil, Matricula,
    FormacaoAcademica, Habilidade, Video, Modulo, Material,
    Certificado, MetaSemanal, Avaliacao, Comentario, Notificacao,
    Ambiente,
)
from core.services.acesso import user_can_access_curso, get_user_role


class VideoSerializer(serializers.ModelSerializer):
    arquivo_url = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = ('id', 'titulo', 'arquivo_url', 'url_externa', 'modulo', 'ordem', 'ativo')

    def get_arquivo_url(self, obj):
        """Retorna URL direta do vídeo. Se for Cloudinary, a URL já é final."""
        if not obj.arquivo:
            return None
        # O .url do CloudinaryStorage já retorna a URL absoluta direta pro CDN
        # FileSystemStorage retorna URL relativa, que precisa do domínio
        url = obj.arquivo.url
        if url.startswith('http://') or url.startswith('https://'):
            return url
        # Apenas para storage local: prefixa com o domínio
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(url)
        return url


class CursoSerializer(serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    pode_acessar = serializers.SerializerMethodField()
    ambiente_nome = serializers.CharField(source='ambiente.nome', read_only=True, default=None)
    videos = VideoSerializer(many=True, read_only=True)
    status_matricula = serializers.SerializerMethodField()

    class Meta:
        model = Curso
        fields = '__all__'

    def get_status_matricula(self, obj):
        """Lê do atributo prefetchado pela view em vez de fazer nova query."""
        request = self.context.get('request')
        user = request.user if request else None
        if not user or not user.is_authenticated:
            return 'nao_iniciado'
        # Usa o prefetch feito na view (_matricula_usuario)
        matriculas = getattr(obj, '_matricula_usuario', None)
        if matriculas and len(matriculas) > 0:
            matricula = matriculas[0]
            if matricula.concluido:
                return 'concluido'
            if matricula.progresso > 0:
                return 'em_andamento'
        return 'nao_iniciado'

    def get_pode_acessar(self, obj):
        # Usa dados de permissão já calculados no contexto do serializer
        user_role = self.context.get('user_role', 'visitor')
        user_planos_ids = self.context.get('user_planos_ids', [])
        user_academias_ids = self.context.get('user_academias_ids', [])
        request = self.context.get('request')
        user = request.user if request else None

        if obj.status != 'publicado':
            if not user or not user.is_authenticated or not user.is_staff:
                return False
        if obj.is_gratuito:
            return True
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user_role in ['admin', 'gestor_orcoma', 'cliente_premium']:
            return True

        roles_extras = obj.roles_extras or []
        if user_role in roles_extras:
            return True

        if not user_academias_ids:
            return False
        # Verifica acesso pelo ambiente principal
        if obj.ambiente_id and obj.ambiente_id in user_academias_ids:
            return True
        # Verifica acesso por academias extras
        academias_extras_ids = list(obj.academias_extras.values_list('id', flat=True))
        if any(aid in user_academias_ids for aid in academias_extras_ids):
            return True

        return False

    def get_video_url(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        pode = self.get_pode_acessar(obj)
        if not pode:
            return None
        if obj.video:
            url = obj.video.url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            if request:
                return request.build_absolute_uri(url)
            return url
        primeiro = obj.videos.filter(ativo=True).order_by('ordem').first()
        if primeiro and primeiro.arquivo:
            url = primeiro.arquivo.url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            if request:
                return request.build_absolute_uri(url)
            return url
        if primeiro and primeiro.url_externa:
            return primeiro.url_externa
        return None

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            url = obj.thumbnail.url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(url)
            return url
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        pode = self.get_pode_acessar(instance)
        if not pode:
            data.pop('video', None)
            data['video_url'] = None
            for video in data.get('videos', []):
                video['arquivo_url'] = None
        return data


class CursoListSerializer(serializers.ModelSerializer):
    """Serializer leve para listagem do catálogo — sem N+1 queries."""
    video_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    pode_acessar = serializers.SerializerMethodField()
    ambiente_nome = serializers.CharField(source='ambiente.nome', read_only=True, default=None)
    status_matricula = serializers.SerializerMethodField()
    primeiro_video_id = serializers.SerializerMethodField()

    class Meta:
        model = Curso
        fields = (
            'id', 'titulo', 'slug', 'tipo', 'descricao', 'status',
            'ambiente', 'ambiente_nome', 'is_gratuito', 'is_recomendado',
            'thumbnail_url', 'video_url',
            'pode_acessar', 'status_matricula',
            'created_at', 'updated_at', 'primeiro_video_id',
        )

    def get_status_matricula(self, obj):
        """Lê do atributo prefetchado pela view em vez de fazer nova query."""
        request = self.context.get('request')
        user = request.user if request else None
        if not user or not user.is_authenticated:
            return 'nao_iniciado'
        matriculas = getattr(obj, '_matricula_usuario', None)
        if matriculas and len(matriculas) > 0:
            matricula = matriculas[0]
            if matricula.concluido:
                return 'concluido'
            if matricula.progresso > 0:
                return 'em_andamento'
        return 'nao_iniciado'

    def get_pode_acessar(self, obj):
        """Usa dados de permissão já calculados no contexto do serializer."""
        user_role = self.context.get('user_role', 'visitor')
        user_academias_ids = self.context.get('user_academias_ids', [])
        request = self.context.get('request')
        user = request.user if request else None

        if obj.status != 'publicado':
            if not user or not user.is_authenticated or not user.is_staff:
                return False
        if obj.is_gratuito:
            return True
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user_role in ['admin', 'gestor_orcoma', 'cliente_premium']:
            return True

        roles_extras = obj.roles_extras or []
        if user_role in roles_extras:
            return True

        if not user_academias_ids:
            return False
        if obj.ambiente_id and obj.ambiente_id in user_academias_ids:
            return True
        academias_extras_ids = list(obj.academias_extras.values_list('id', flat=True))
        if any(aid in user_academias_ids for aid in academias_extras_ids):
            return True

        return False

    def get_video_url(self, obj):
        """Retorna URL do primeiro vídeo do curso (catálogo)."""
        pode = self.get_pode_acessar(obj)
        if not pode:
            return None
        if obj.video:
            url = obj.video.url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(url)
            return url
        # Usa o primeiro vídeo (já anotado via Subquery na view)
        primeiro = obj.videos.filter(ativo=True).order_by('ordem').first()
        if primeiro and primeiro.arquivo:
            url = primeiro.arquivo.url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(url)
            return url
        if primeiro and primeiro.url_externa:
            return primeiro.url_externa
        return None

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            url = obj.thumbnail.url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(url)
            return url
        return None

    def get_primeiro_video_id(self, obj):
        """Usa o ID anotado via Subquery na view."""
        return getattr(obj, '_primeiro_video_id', None)


class AmbienteSerializer(serializers.ModelSerializer):
    imagem_url = serializers.SerializerMethodField()

    class Meta:
        model = Ambiente
        fields = ('id', 'nome', 'descricao', 'ativo', 'imagem_url')

    def get_imagem_url(self, obj):
        if not obj.imagem:
            return None
        url = obj.imagem.url
        if url.startswith('http://') or url.startswith('https://'):
            return url
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(url)
        return url


class TrilhaSerializer(serializers.ModelSerializer):
    cursos = serializers.SerializerMethodField()
    ambiente_nome = serializers.CharField(source='ambiente.nome', read_only=True)

    class Meta:
        model = Trilha
        fields = '__all__'

    def get_cursos(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        cursos = obj.cursos.filter(status='publicado')
        from core.services.acesso import filtrar_cursos_acessiveis
        cursos = filtrar_cursos_acessiveis(cursos, user)
        return CursoSerializer(cursos, many=True, context=self.context).data


class TrilhaListSerializer(serializers.ModelSerializer):
    ambiente_nome = serializers.CharField(source='ambiente.nome', read_only=True)
    cursos_count = serializers.SerializerMethodField()

    class Meta:
        model = Trilha
        fields = ('id', 'nome', 'ambiente', 'ambiente_nome', 'descricao', 'cursos_count')

    def get_cursos_count(self, obj):
        from core.services.acesso import filtrar_cursos_acessiveis
        request = self.context.get('request')
        user = request.user if request else None
        cursos = obj.cursos.filter(status='publicado')
        return filtrar_cursos_acessiveis(cursos, user).count()


class EventoSerializer(serializers.ModelSerializer):
    imagem_url = serializers.SerializerMethodField()

    class Meta:
        model = Evento
        fields = '__all__'

    def get_imagem_url(self, obj):
        if obj.imagem:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.imagem.url)
            return obj.imagem.url
        return None


class NovidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Novidade
        fields = '__all__'


class LogAtividadeSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = LogAtividade
        fields = ('id', 'usuario', 'usuario_nome', 'acao', 'detalhes', 'created_at')


class MatriculaSerializer(serializers.ModelSerializer):
    curso_titulo = serializers.CharField(source='curso.titulo', read_only=True)
    video_corrente_id = serializers.IntegerField(source='video_corrente.id', read_only=True, default=None)
    video_corrente_titulo = serializers.CharField(source='video_corrente.titulo', read_only=True, default=None)

    class Meta:
        model = Matricula
        fields = ('id', 'usuario', 'curso', 'curso_titulo', 'data_inscricao', 'progresso', 'concluido', 'concluido_em', 'ultimo_segundo_assistido', 'video_corrente', 'video_corrente_id', 'video_corrente_titulo', 'aulas_concluidas', 'ultima_aula')
        read_only_fields = ('id', 'usuario', 'data_inscricao', 'concluido_em', 'video_corrente_id', 'video_corrente_titulo')


class MatriculaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Matricula
        fields = ('id', 'curso')
        read_only_fields = ('id',)

    def validate_curso(self, curso):
        request = self.context.get('request')
        user = request.user if request else None
        if not user_can_access_curso(curso, user):
            raise serializers.ValidationError('Você não tem permissão para acessar este curso.')
        return curso


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')


class PerfilSerializer(serializers.ModelSerializer):
    planos = serializers.StringRelatedField(many=True, read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = Perfil
        fields = ('role', 'role_display', 'planos', 'empresa', 'telefone', 'bio', 'avatar')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'first_name', 'last_name')

    def validate_username(self, value):
        """Se o username já existir, gera um único automaticamente."""
        if User.objects.filter(username=value).exists():
            import uuid
            return f'user_{uuid.uuid4().hex[:8]}'
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        perfil = user.perfil
        perfil.role = 'visitor'
        perfil.save()
        return user


class FormacaoAcademicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormacaoAcademica
        fields = ('id', 'instituicao', 'nivel', 'area', 'inicio_mes', 'inicio_ano', 'termino_mes', 'termino_ano')
        read_only_fields = ('id',)


class HabilidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Habilidade
        fields = ('id', 'nome')
        read_only_fields = ('id',)


class MeSerializer(serializers.ModelSerializer):
    perfil = PerfilSerializer(read_only=True)
    cpf = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cnpj = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    nome = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    plano_nome = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'nome', 'role', 'perfil', 'cpf', 'cnpj', 'plano_nome', 'avatar_url', 'date_joined')
        read_only_fields = ('username', 'email')

    def get_nome(self, obj):
        return obj.get_full_name() or obj.username

    def get_role(self, obj):
        return get_user_role(obj)

    def get_plano_nome(self, obj):
        perfil = getattr(obj, 'perfil', None)
        if perfil:
            planos = perfil.planos.filter(ativo=True)
            if planos.exists():
                return planos.first().nome
            return perfil.get_role_display()
        return 'Visitante'

    def get_avatar_url(self, obj):
        perfil = getattr(obj, 'perfil', None)
        if perfil and perfil.avatar:
            return perfil.avatar.url
        return ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        perfil_obj = getattr(instance, 'perfil', None)
        if perfil_obj:
            data['cpf'] = perfil_obj.cpf or ''
            data['cnpj'] = perfil_obj.cnpj or ''
        else:
            data['cpf'] = ''
            data['cnpj'] = ''
        return data

    def update(self, instance, validated_data):
        # Atualiza campos do User (first_name, last_name)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.save()
        # Atualiza campos do Perfil (cpf, cnpj) - vêm como chaves soltas no validated_data
        perfil_obj = instance.perfil
        if 'cpf' in validated_data:
            perfil_obj.cpf = validated_data['cpf'] or ''
        if 'cnpj' in validated_data:
            perfil_obj.cnpj = validated_data['cnpj'] or ''
        perfil_obj.save()
        return instance


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        return super().get_token(user)

    def validate(self, attrs):
        login = attrs.get(self.username_field)
        if login and '@' in login:
            email = login.strip().lower()
            user = User.objects.filter(email__iexact=email).first()
            if user:
                attrs[self.username_field] = user.get_username()

        data = super().validate(attrs)
        user = self.user
        perfil = getattr(user, 'perfil', None)

        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': get_user_role(user),
            'role_display': perfil.get_role_display() if perfil else 'Visitante',
            'avatar_url': perfil.avatar.url if perfil and perfil.avatar else '',
        }
        return data


class ModuloSerializer(serializers.ModelSerializer):
    curso_titulo = serializers.CharField(source='curso.titulo', read_only=True)
    materiais = serializers.SerializerMethodField()

    class Meta:
        model = Modulo
        fields = ('id', 'curso', 'curso_titulo', 'titulo', 'descricao', 'ordem', 'ativo', 'materiais')

    def get_materiais(self, obj):
        request = self.context.get('request')
        materiais = obj.materiais.filter(ativo=True).order_by('ordem')
        return MaterialSerializer(materiais, many=True, context=self.context).data


class MaterialSerializer(serializers.ModelSerializer):
    arquivo_url = serializers.SerializerMethodField()
    curso_titulo = serializers.CharField(source='modulo.curso.titulo', read_only=True)

    class Meta:
        model = Material
        fields = ('id', 'modulo', 'curso_titulo', 'titulo', 'arquivo', 'arquivo_url', 'url_externa', 'modalidade', 'ordem', 'ativo')

    def get_arquivo_url(self, obj):
        if not obj.arquivo:
            return None
        request = self.context.get('request')
        user = request.user if request else None
        # Check access through the course
        if user_can_access_curso(obj.modulo.curso, user):
            if request:
                return request.build_absolute_uri(obj.arquivo.url)
            return obj.arquivo.url
        return None


class CertificadoSerializer(serializers.ModelSerializer):
    curso_titulo = serializers.CharField(source='matricula.curso.titulo', read_only=True)
    curso_duracao = serializers.SerializerMethodField()
    aluno_nome = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificado
        fields = ('id', 'codigo', 'emitido_em', 'curso_titulo', 'curso_duracao', 'aluno_nome', 'download_url')

    def get_curso_duracao(self, obj):
        videos = obj.matricula.curso.videos.filter(ativo=True)
        total_segundos = 0
        for v in videos:
            if hasattr(v, 'duracao') and v.duracao:
                total_segundos += v.duracao
        if total_segundos > 0:
            horas = total_segundos // 3600
            minutos = (total_segundos % 3600) // 60
            return f'{horas}h{minutos:02d}m' if horas > 0 else f'{minutos}min'
        return None

    def get_aluno_nome(self, obj):
        user = obj.matricula.usuario
        return user.get_full_name() or user.username

    def get_download_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/certificados/{obj.id}/download/')
        return f'/api/certificados/{obj.id}/download/'


class AvaliacaoSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.SerializerMethodField()
    usuario_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Avaliacao
        fields = ('id', 'usuario', 'usuario_nome', 'usuario_avatar', 'modulo', 'nota', 'comentario', 'created_at')
        read_only_fields = ('id', 'usuario', 'usuario_nome', 'usuario_avatar', 'created_at')

    def get_usuario_nome(self, obj):
        return obj.usuario.get_full_name() or obj.usuario.username

    def get_usuario_avatar(self, obj):
        request = self.context.get('request')
        perfil = getattr(obj.usuario, 'perfil', None)
        if perfil and perfil.avatar:
            if request:
                return request.build_absolute_uri(obj.usuario.perfil.avatar.url)
            return obj.usuario.perfil.avatar.url
        return ''


class ComentarioSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.SerializerMethodField()
    usuario_avatar = serializers.SerializerMethodField()
    respostas = serializers.SerializerMethodField()
    curtidas = serializers.SerializerMethodField()
    curtido_por_mim = serializers.SerializerMethodField()

    class Meta:
        model = Comentario
        fields = (
            'id', 'usuario', 'usuario_nome', 'usuario_avatar', 'modulo', 'texto',
            'comentario_pai', 'respostas', 'curtidas', 'curtido_por_mim', 'created_at',
        )
        read_only_fields = ('id', 'usuario', 'created_at')

    def get_usuario_nome(self, obj):
        return obj.usuario.get_full_name() or obj.usuario.username

    def get_usuario_avatar(self, obj):
        request = self.context.get('request')
        perfil = getattr(obj.usuario, 'perfil', None)
        if perfil and perfil.avatar:
            if request:
                return request.build_absolute_uri(obj.usuario.perfil.avatar.url)
            return obj.usuario.perfil.avatar.url
        return ''

    def get_respostas(self, obj):
        respostas = obj.respostas.all().select_related('usuario')
        return ComentarioSerializer(respostas, many=True, context=self.context).data

    def get_curtidas(self, obj):
        return obj.curtido_por.count()

    def get_curtido_por_mim(self, obj):
        user = self.context.get('request').user
        return bool(user and user.is_authenticated and obj.curtido_por.filter(pk=user.pk).exists())


class MetaSemanalSerializer(serializers.ModelSerializer):
    percentual = serializers.ReadOnlyField()

    class Meta:
        model = MetaSemanal
        fields = ('id', 'titulo', 'meta_horas', 'horas_concluidas', 'semana_inicio', 'semana_fim', 'concluida', 'percentual')


class NotificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacao
        fields = ('id', 'titulo', 'mensagem', 'tipo', 'lida', 'link', 'created_at')
        read_only_fields = ('id', 'created_at')

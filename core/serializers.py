import re

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import (
    Curso, Trilha, Evento, Novidade, LogAtividade, Perfil, Matricula,
    FormacaoAcademica, Habilidade, AssinaturaPlano, Video, Modulo, Material,
    Certificado,
)
from core.services.acesso import user_can_access_curso, get_user_role


class VideoSerializer(serializers.ModelSerializer):
    arquivo_url = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = ('id', 'titulo', 'arquivo_url', 'url_externa', 'ordem', 'ativo')

    def get_arquivo_url(self, obj):
        if not obj.arquivo:
            return None
        request = self.context.get('request')
        curso = obj.curso
        user = request.user if request else None
        if not user_can_access_curso(curso, user):
            return None
        if request:
            return request.build_absolute_uri(obj.arquivo.url)
        return obj.arquivo.url


class CursoSerializer(serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    pode_acessar = serializers.SerializerMethodField()
    ambiente_nome = serializers.CharField(source='ambiente.nome', read_only=True, default=None)
    videos = VideoSerializer(many=True, read_only=True)

    class Meta:
        model = Curso
        fields = '__all__'

    def get_pode_acessar(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        return user_can_access_curso(obj, user)

    def get_video_url(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        if not user_can_access_curso(obj, user):
            return None
        if obj.video:
            if request:
                return request.build_absolute_uri(obj.video.url)
            return obj.video.url
        primeiro = obj.videos.filter(ativo=True).order_by('ordem').first()
        if primeiro and primeiro.arquivo:
            if request:
                return request.build_absolute_uri(primeiro.arquivo.url)
            return primeiro.arquivo.url
        if primeiro and primeiro.url_externa:
            return primeiro.url_externa
        return None

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = request.user if request else None
        if not user_can_access_curso(instance, user):
            data.pop('video', None)
            data['video_url'] = None
            for video in data.get('videos', []):
                video['arquivo_url'] = None
        return data


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

    class Meta:
        model = Trilha
        fields = ('id', 'nome', 'ambiente', 'ambiente_nome', 'descricao')


class EventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evento
        fields = '__all__'


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

    class Meta:
        model = Matricula
        fields = ('id', 'usuario', 'curso', 'curso_titulo', 'data_inscricao', 'progresso', 'concluido', 'concluido_em', 'ultimo_segundo_assistido', 'video_corrente', 'video_corrente_id')
        read_only_fields = ('id', 'usuario', 'data_inscricao', 'concluido_em', 'video_corrente_id')


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
        fields = ('role', 'role_display', 'planos', 'empresa', 'telefone', 'bio')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'first_name', 'last_name')

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
    nome = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    plano_nome = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'nome', 'role', 'perfil', 'plano_nome', 'date_joined')

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
        }
        return data


class AssinaturaPlanoSerializer(serializers.ModelSerializer):
    plano_nome = serializers.CharField(source='plano.nome', read_only=True)
    plano_descricao = serializers.CharField(source='plano.descricao', read_only=True)
    dias_restantes = serializers.SerializerMethodField()
    total_dias = serializers.SerializerMethodField()
    percentual_usado = serializers.SerializerMethodField()

    class Meta:
        model = AssinaturaPlano
        fields = (
            'id', 'plano_nome', 'plano_descricao',
            'data_contratacao', 'data_expiracao',
            'status', 'dias_restantes', 'total_dias', 'percentual_usado',
        )

    def get_dias_restantes(self, obj):
        from datetime import date
        delta = obj.data_expiracao - date.today()
        return max(delta.days, 0)

    def get_total_dias(self, obj):
        delta = obj.data_expiracao - obj.data_contratacao
        return max(delta.days, 0)

    def get_percentual_usado(self, obj):
        from datetime import date
        total = (obj.data_expiracao - obj.data_contratacao).days
        if total <= 0:
            return 100
        usado = total - max((obj.data_expiracao - date.today()).days, 0)
        return min(round((usado / total) * 100), 100)


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

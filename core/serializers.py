import re

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Curso, Trilha, Evento, Novidade, LogAtividade, Perfil


class CursoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Curso
        fields = '__all__'


class TrilhaSerializer(serializers.ModelSerializer):
    cursos = CursoSerializer(many=True, read_only=True)

    class Meta:
        model = Trilha
        fields = '__all__'


class TrilhaListSerializer(serializers.ModelSerializer):
    ambiente_nome = serializers.StringRelatedField(source='ambiente', read_only=True)

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


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')


class PerfilSerializer(serializers.ModelSerializer):
    planos = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = Perfil
        fields = ('role', 'planos', 'empresa', 'telefone', 'bio')


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
        return user


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
        perfil = getattr(obj, 'perfil', None)
        if perfil:
            return perfil.role
        return 'visitor'

    def get_plano_nome(self, obj):
        perfil = getattr(obj, 'perfil', None)
        if perfil:
            return perfil.get_role_display()
        return 'Visitante'


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        return token

    def _get_supabase_profile(self, email):
        if not email:
            return None

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT nome, email, role FROM profiles WHERE lower(email) = %s LIMIT 1',
                    [email.lower()],
                )
                row = cursor.fetchone()
        except Exception:
            return None

        if not row:
            return None

        return {
            'nome': row[0],
            'email': row[1],
            'role': row[2],
        }

    def _create_django_user_for_supabase_profile(self, email, supabase_profile, password):
        username_base = email.split('@')[0]
        username = username_base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{username_base}{counter}"
            counter += 1

        nome = supabase_profile.get('nome') or username_base
        nome_partes = nome.split(' ', 1)
        first_name = nome_partes[0] if nome_partes else ''
        last_name = nome_partes[1] if len(nome_partes) > 1 else ''

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        user.save()
        return user

    def validate(self, attrs):
        login = attrs.get(self.username_field)
        password = attrs.get('password')

        if login and '@' in login:
            email = login.strip().lower()
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                supabase_profile = self._get_supabase_profile(email)
                profile_password = getattr(settings, 'PROFILE_LOGIN_PASSWORD', 'admin')
                if supabase_profile and password == profile_password:
                    user = self._create_django_user_for_supabase_profile(email, supabase_profile, profile_password)
            if user:
                attrs[self.username_field] = user.get_username()

        data = super().validate(attrs)
        user = self.user
        perfil = getattr(user, 'perfil', None)
        supabase_profile = self._get_supabase_profile(user.email)
        nome = supabase_profile.get('nome') if supabase_profile else ''
        nome_partes = nome.split(' ', 1) if nome else []

        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': supabase_profile.get('email') if supabase_profile else user.email,
            'first_name': nome_partes[0] if nome_partes else user.first_name,
            'last_name': nome_partes[1] if len(nome_partes) > 1 else user.last_name,
            'role': supabase_profile.get('role') if supabase_profile else (perfil.role if perfil else 'visitor'),
        }
        return data

import logging
from rest_framework import viewsets, permissions, generics, status
from rest_framework.views import APIView
from django.core.cache import cache

logger = logging.getLogger(__name__)
from .models import Curso, Trilha, Evento, EventoLeitura, Novidade, LogAtividade, CursoVisualizacao, Matricula, FormacaoAcademica, Habilidade, Ambiente, Modulo, Material, Certificado, MetaSemanal, Video, Notificacao, Avaliacao, Comentario
from core.services.acesso import filtrar_cursos_acessiveis, user_can_access_curso, get_academias_permitidas, get_user_role, get_academias_permitidas_para_role
from .serializers import (
    CursoSerializer, CursoListSerializer, TrilhaSerializer, TrilhaListSerializer,
    EventoSerializer, NovidadeSerializer, LogAtividadeSerializer,
    RegisterSerializer, MeSerializer, CustomTokenObtainPairSerializer,
    MatriculaSerializer, MatriculaCreateSerializer,
    FormacaoAcademicaSerializer, HabilidadeSerializer,
    ModuloSerializer, MaterialSerializer,
    CertificadoSerializer, MetaSemanalSerializer, AvaliacaoSerializer, ComentarioSerializer,
    NotificacaoSerializer, AmbienteSerializer
)
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from django.db import connection, models
from django.utils import timezone
from datetime import timedelta
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.throttling import ScopedRateThrottle
from core.recaptcha import verify_recaptcha_token


@api_view(['GET'])
@permission_classes([AllowAny])
def ping(request):
    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_ambientes(request):
    from core.services.acesso import get_academias_permitidas
    user = request.user
    qs = get_academias_permitidas(user)
    serializer = AmbienteSerializer(qs, many=True, context={'request': request})
    return Response(serializer.data)


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_staff


from rest_framework.pagination import PageNumberPagination


class CursoPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CursoViewSet(viewsets.ModelViewSet):
    serializer_class = CursoSerializer
    permission_classes = [IsStaffOrReadOnly]
    pagination_class = None

    def get_serializer_class(self):
        if self.action == 'list':
            return CursoListSerializer
        return CursoSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user

        # Calcula dados de permissão uma ÚNICA vez para toda a requisição
        role = None
        planos_ids = []
        academias_ids = []
        if user.is_authenticated:
            from core.services.acesso import get_user_role, ROLES_ACESSO_TOTAL
            role = get_user_role(user)
            perfil = getattr(user, 'perfil', None)
            if perfil:
                planos_ids = list(perfil.planos.filter(ativo=True).values_list('id', flat=True))
            if role in ROLES_ACESSO_TOTAL:
                from core.models import Ambiente
                qs = Ambiente.objects.filter(ativo=True)
                if role == 'cliente_premium':
                    qs = qs.exclude(nome__iexact='Academy Orcomakers')
                academias_ids = list(qs.values_list('id', flat=True))
            else:
                from core.services.acesso import PERMISSOES_PAPEL
                nomes = PERMISSOES_PAPEL.get(role, [])
                if nomes:
                    from core.models import Ambiente
                    academias_ids = list(Ambiente.objects.filter(ativo=True, nome__in=nomes).values_list('id', flat=True))
        else:
            role = 'visitor'

        context['user_role'] = role
        context['user_planos_ids'] = planos_ids
        context['user_academias_ids'] = academias_ids
        return context

    def get_queryset(self):
        from django.db.models import Prefetch, OuterRef, Subquery
        user = self.request.user

        qs = Curso.objects.select_related('ambiente').prefetch_related('academias_extras')

        # Prefetch eficiente: anota a matrícula do usuário atual em cada curso
        if user.is_authenticated:
            qs = qs.prefetch_related(
                Prefetch(
                    'matriculas',
                    queryset=Matricula.objects.filter(usuario=user),
                    to_attr='_matricula_usuario'
                )
            )
            # Também prefetch do primeiro vídeo ativo para a listagem
            primeiro_video_qs = Video.objects.filter(
                curso=OuterRef('pk'), ativo=True
            ).order_by('ordem')
            qs = qs.annotate(
                _primeiro_video_id=Subquery(primeiro_video_qs.values('id')[:1])
            )
        else:
            # Visitante: anota None para matrícula
            qs = qs.prefetch_related(
                Prefetch(
                    'matriculas',
                    queryset=Matricula.objects.none(),
                    to_attr='_matricula_usuario'
                )
            )

        if not (user.is_authenticated and user.is_staff):
            qs = qs.filter(status='publicado')

        qs = filtrar_cursos_acessiveis(qs, user)

        ambiente = self.request.query_params.get('ambiente')
        if ambiente:
            qs = qs.filter(
                Q(ambiente__nome__iexact=ambiente) | Q(ambiente__id=ambiente)
            )

        status_param = self.request.query_params.get('status')
        if status_param and user.is_authenticated and user.is_staff:
            qs = Curso.objects.select_related('ambiente').prefetch_related('academias_extras')
            qs = qs.filter(status=status_param)
            if ambiente:
                qs = qs.filter(
                    Q(ambiente__nome__iexact=ambiente) | Q(ambiente__id=ambiente)
                )

        return qs.distinct()

    def list(self, request, *args, **kwargs):
        # Cache público (sem user_id) — apenas para visitantes não autenticados
        # Usuários logados têm permissões diferentes, então não cacheamos
        user = request.user
        if not user.is_authenticated:
            ambiente = request.query_params.get('ambiente', '')
            cache_key = f'cursos_list_public_{ambiente}'
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)
        
        response = super().list(request, *args, **kwargs)
        
        if not user.is_authenticated and response.status_code == 200:
            ambiente = request.query_params.get('ambiente', '')
            cache_key = f'cursos_list_public_{ambiente}'
            cache.set(cache_key, response.data, 60)  # 60 segundos
        
        return response

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not user_can_access_curso(instance, request.user):
            return Response(
                {'detail': 'Você não tem permissão para acessar este curso.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class TrilhaViewSet(viewsets.ReadOnlyModelViewSet):
    def get_queryset(self):
        user = self.request.user
        qs = Trilha.objects.select_related('ambiente').prefetch_related('cursos')
        academias = get_academias_permitidas(user)
        if user.is_authenticated and (user.is_superuser or user.is_staff):
            return qs
        if not user.is_authenticated:
            return qs.filter(
                cursos__is_gratuito=True,
                cursos__status='publicado',
            ).distinct()
        return qs.filter(ambiente__in=academias).distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return TrilhaListSerializer
        return TrilhaSerializer


class EventoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Evento.objects.all()
    serializer_class = EventoSerializer

    @action(detail=False, methods=['get'], url_path='proximo')
    def proximo(self, request):
        agora = timezone.now()
        evento = Evento.objects.filter(data__gte=agora).order_by('data').first()
        if not evento:
            return Response({'evento': None, 'ultima_leitura': None, 'requer_leitura': False})

        ultima_leitura = None
        requer_leitura = False
        if request.user.is_authenticated:
            leitura = EventoLeitura.objects.filter(usuario=request.user, evento=evento).first()
            if leitura:
                ultima_leitura = leitura.lida_em.isoformat()
                requer_leitura = (agora - leitura.lida_em) >= timedelta(hours=24)
            else:
                requer_leitura = True
        return Response({
            'evento': EventoSerializer(evento, context={'request': request}).data,
            'ultima_leitura': ultima_leitura,
            'requer_leitura': requer_leitura,
        })

    @action(detail=True, methods=['post'], url_path='marcar-lida', permission_classes=[IsAuthenticated])
    def marcar_lida(self, request, pk=None):
        evento = self.get_object()
        leitura, _ = EventoLeitura.objects.update_or_create(
            usuario=request.user,
            evento=evento,
            defaults={'lida_em': timezone.now()},
        )
        return Response({'ultima_leitura': leitura.lida_em.isoformat()})


class MetaSemanalViewSet(viewsets.ModelViewSet):
    serializer_class = MetaSemanalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MetaSemanal.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        total = Matricula.objects.filter(usuario=self.request.user).aggregate(
            total=models.Sum('tempo_total_assistido')
        )['total'] or 0
        serializer.save(usuario=self.request.user, baseline_tempo=total)


class NovidadeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Novidade.objects.filter(ativo=True)
    serializer_class = NovidadeSerializer


class MatriculaViewSet(viewsets.ModelViewSet):
    serializer_class = MatriculaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Matricula.objects.filter(usuario=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return MatriculaCreateSerializer
        return MatriculaSerializer

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @action(detail=False, methods=['get'], url_path='minhas')
    def minhas(self, request):
        matriculas = Matricula.objects.filter(usuario=request.user)
        serializer = MatriculaSerializer(matriculas, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='concluir')
    def concluir(self, request):
        curso_id = request.data.get('curso')
        if not curso_id:
            return Response({'detail': 'curso é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
        matricula, created = Matricula.objects.get_or_create(
            usuario=request.user,
            curso_id=curso_id,
            defaults={'progresso': 100, 'concluido': True, 'concluido_em': timezone.now()}
        )
        if not created:
            matricula.progresso = 100
            matricula.concluido = True
            matricula.concluido_em = timezone.now()
            matricula.save()

        Certificado.objects.get_or_create(matricula=matricula)

        curso = matricula.curso
        Notificacao.objects.create(
            usuario=request.user,
            titulo='Curso Concluído!',
            mensagem=f'Parabéns! Você concluiu {curso.titulo}. Seu certificado está disponível.',
            tipo='curso_concluido',
            link='/certificados',
        )

        serializer = MatriculaSerializer(matricula)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='atualizar-progresso')
    def atualizar_progresso(self, request):
        curso_id = request.data.get('curso')
        progresso = request.data.get('progresso', 0)
        if not curso_id:
            return Response({'detail': 'curso é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
        matricula, created = Matricula.objects.get_or_create(
            usuario=request.user,
            curso_id=curso_id,
            defaults={'progresso': progresso}
        )
        if not created:
            matricula.progresso = progresso
            matricula.save()
        serializer = MatriculaSerializer(matricula)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='status')
    def status_curso(self, request):
        curso_id = request.query_params.get('curso')
        if not curso_id:
            return Response({'detail': 'curso é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            matricula = Matricula.objects.get(usuario=request.user, curso_id=curso_id)
            serializer = MatriculaSerializer(matricula)
            return Response(serializer.data)
        except Matricula.DoesNotExist:
            return Response({'concluido': False, 'progresso': 0})

    @action(detail=False, methods=['post'], url_path='salvar-posicao')
    def salvar_posicao(self, request):
        curso_id = request.data.get('curso')
        video_id = request.data.get('video_id')
        segundo = request.data.get('segundo', 0)
        if not curso_id:
            return Response({'detail': 'curso é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
        matricula, created = Matricula.objects.get_or_create(
            usuario=request.user,
            curso_id=curso_id,
            defaults={'ultimo_segundo_assistido': segundo, 'video_corrente_id': video_id}
        )
        if not created:
            if segundo > matricula.ultimo_segundo_assistido:
                delta = segundo - matricula.ultimo_segundo_assistido
                matricula.tempo_total_assistido += min(delta, 30)
            matricula.ultimo_segundo_assistido = segundo
            if video_id:
                matricula.video_corrente_id = video_id
            matricula.save()
        return Response({'ok': True, 'segundo': segundo, 'video_id': video_id})

    @action(detail=False, methods=['get'], url_path='posicao')
    def obter_posicao(self, request):
        curso_id = request.query_params.get('curso')
        if not curso_id:
            return Response({'detail': 'curso é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            matricula = Matricula.objects.get(usuario=request.user, curso_id=curso_id)
            return Response({
                'video_id': matricula.video_corrente_id,
                'segundo': matricula.ultimo_segundo_assistido,
                'progresso': matricula.progresso,
                'concluido': matricula.concluido,
            })
        except Matricula.DoesNotExist:
            return Response({'video_id': None, 'segundo': 0, 'progresso': 0, 'concluido': False})


from rest_framework_simplejwt.tokens import RefreshToken
from django.http import JsonResponse
from core.authentication import set_jwt_cookies, clear_jwt_cookies


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        verify_recaptcha_token(request.data.get('recaptcha_token'))
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            data = response.data
            access = data.get('access')
            refresh = data.get('refresh')
            if access:
                response = set_jwt_cookies(response, access, refresh)
                # Tokens trafegam apenas em cookie httpOnly — não retornar no corpo.
                response.data = {'user': data.get('user', {})}
        return response


class CookieTokenRefreshView(APIView):
    """Renova o access token lendo o refresh token do cookie httpOnly (sem expor tokens no corpo)."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'refresh'

    def post(self, request):
        refresh = request.COOKIES.get(settings.JWT_COOKIE_REFRESH)
        if not refresh:
            return Response({'detail': 'Refresh token ausente.'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = TokenRefreshSerializer(data={'refresh': refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            return Response({'detail': 'Sessão expirada. Faça login novamente.'}, status=status.HTTP_401_UNAUTHORIZED)

        response = Response({'ok': True})
        set_jwt_cookies(
            response,
            serializer.validated_data['access'],
            serializer.validated_data.get('refresh'),
        )
        return response


@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    response = JsonResponse({'detail': 'Logout realizado.'}, status=status.HTTP_200_OK)
    return clear_jwt_cookies(response)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'registro'

    def perform_create(self, serializer):
        verify_recaptcha_token(self.request.data.get('recaptcha_token'))
        user = serializer.save()
        Notificacao.objects.create(
            usuario=user,
            titulo='Bem-vindo à Orcoma Academy!',
            mensagem='Olá! Que bom ter você conosco. Explore nossos cursos, eventos e trilhas de aprendizagem.',
            tipo='boas_vindas',
            link='/meus-cursos',
        )


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user


class AvatarUploadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        avatar_file = request.FILES.get('avatar')
        if not avatar_file:
            return Response(
                {'error': 'Nenhum arquivo enviado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        if avatar_file.content_type not in allowed_types:
            return Response(
                {'error': 'Formato não suportado. Use JPG, PNG ou WebP.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if avatar_file.size > 5 * 1024 * 1024:
            return Response(
                {'error': 'Arquivo muito grande. Máximo 5MB.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not hasattr(request.user, 'perfil'):
            return Response(
                {'error': 'Perfil não encontrado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            perfil = request.user.perfil
            perfil.avatar = avatar_file
            perfil.save()
        except Exception as e:
            logger.error("Avatar upload failed for user %s: %s", request.user.pk, e, exc_info=True)
            return Response(
                {'error': 'Erro ao salvar avatar. Tente novamente.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            'avatar_url': perfil.avatar.url,
            'message': 'Avatar atualizado com sucesso.'
        }, status=status.HTTP_200_OK)


class LogAtividadeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LogAtividade.objects.all()
    serializer_class = LogAtividadeSerializer
    permission_classes = [IsAuthenticated]


class FormacaoAcademicaViewSet(viewsets.ModelViewSet):
    serializer_class = FormacaoAcademicaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FormacaoAcademica.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class HabilidadeViewSet(viewsets.ModelViewSet):
    serializer_class = HabilidadeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Habilidade.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class NotificacaoViewSet(viewsets.ModelViewSet):
    serializer_class = NotificacaoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notificacao.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @action(detail=False, methods=['post'], url_path='marcar-todas-lidas')
    def marcar_todas_lidas(self, request):
        Notificacao.objects.filter(usuario=request.user, lida=False).update(lida=True)
        return Response({'detail': 'Todas as notificações foram marcadas como lidas.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='nao-lidas/count')
    def count_nao_lidas(self, request):
        count = Notificacao.objects.filter(usuario=request.user, lida=False).count()
        return Response({'count': count}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='marcar-lida')
    def marcar_lida(self, request):
        notif_id = request.data.get('id')
        if not notif_id:
            return Response({'detail': 'id é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
        Notificacao.objects.filter(usuario=request.user, id=notif_id).update(lida=True)
        return Response({'detail': 'Notificação marcada como lida.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='criar-lembrete-eventos')
    def criar_lembrete_eventos(self, request):
        agora = timezone.now()
        from datetime import timedelta
        inicio = agora + timedelta(hours=23)
        fim = agora + timedelta(hours=25)
        eventos = Evento.objects.filter(data__gte=inicio, data__lte=fim)
        criadas = 0
        for evento in eventos:
            ja_tem = Notificacao.objects.filter(
                usuario=request.user,
                tipo='evento',
                mensagem__contains=evento.titulo,
                created_at__date=agora.date(),
            ).exists()
            if not ja_tem:
                hora = evento.data.astimezone(timezone.get_current_timezone()).strftime('%H:%M')
                Notificacao.objects.create(
                    usuario=request.user,
                    titulo='Lembrete de Evento!',
                    mensagem=f'Amanhã: {evento.titulo} às {hora}',
                    tipo='evento',
                    link='/eventos',
                )
                criadas += 1
        return Response({'criadas': criadas}, status=status.HTTP_200_OK)


from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse
from pathlib import Path
import json

@staff_member_required
@require_POST
def corrigir_texto(request):
    try:
        dados = json.loads(request.body)
        texto = dados.get('texto', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'erro': 'JSON inválido'}, status=400)

    if not texto:
        return JsonResponse({'erro': 'Texto vazio'}, status=400)

    api_key = settings.GOOGLE_API_KEY
    if not api_key:
        return JsonResponse({'erro': 'Serviço de correção indisponível. Configure a GOOGLE_API_KEY.'}, status=503)

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = (
            "Corrija o texto abaixo corrigindo erros de ortografia e gramática, "
            "e reescreva de forma mais profissional. Mantenha o sentido original. "
            "Responda APENAS com o texto corrigido, sem explicações.\n\n"
            f"Texto: {texto}"
        )
        resposta = client.models.generate_content(
            model='gemini-2.0-flash-lite',
            contents=prompt,
        )
        texto_corrigido = resposta.text.strip()
        return JsonResponse({'corrigido': texto_corrigido})
    except Exception as e:
        return JsonResponse({'erro': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def dashboard_stats(request):
    # Cache com user_id (para autenticados) ou chave pública (visitantes)
    user = request.user
    cache_key = f'dashboard_stats_{user.id if user.is_authenticated else "public"}'
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    agora = timezone.now()
    sete_dias_atras = agora - timedelta(days=7)
    trinta_dias_atras = agora - timedelta(days=30)

    metricas = {
        'total_usuarios': User.objects.count(),
        'novos_semana': User.objects.filter(date_joined__gte=sete_dias_atras).count(),
        'cursos_ativos': Curso.objects.filter(status='publicado', tipo='curso').count(),
        'videos_ativos': Curso.objects.filter(status='publicado', tipo='video').count(),
        'eventos_futuros': Evento.objects.filter(data__gte=agora).count(),
        'trilhas_publicadas': Trilha.objects.count(),
        'certificados_emitidos': Certificado.objects.count(),
        'usuarios_ativos_7d': User.objects.filter(is_active=True).count(),
    }

    total_matriculas = Matricula.objects.count()
    matriculas_concluidas = Matricula.objects.filter(concluido=True).count()
    metricas['satisfacao_alunos'] = round((matriculas_concluidas / total_matriculas) * 100) if total_matriculas > 0 else 0

    crescimento = []
    from django.db.models.functions import TruncMonth
    meses = (
        User.objects
        .annotate(mes=TruncMonth('date_joined'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )
    meses_por_label = {}
    for m in meses:
        if m['mes']:
            label = m['mes'].strftime('%b %Y')
            meses_por_label[m['mes'].strftime('%Y-%m')] = {
                'mes': m['mes'].strftime('%Y-%m'),
                'label': label,
                'total': m['total'],
            }
    acumulado = 0
    for chave in sorted(meses_por_label.keys()):
        acumulado += meses_por_label[chave]['total']
        meses_por_label[chave]['acumulado'] = acumulado
    crescimento = list(meses_por_label.values())

    logs = LogAtividade.objects.all()[:10]
    ultimas_atividades = LogAtividadeSerializer(logs, many=True).data

    top_cursos = (
        CursoVisualizacao.objects
        .values('curso__titulo', 'curso__status')
        .annotate(total_visualizacoes=Count('id'))
        .order_by('-total_visualizacoes')[:5]
    )
    destaques_cursos = [
        {'titulo': c['curso__titulo'], 'status': c['curso__status'], 'total_visualizacoes': c['total_visualizacoes']}
        for c in top_cursos
    ]
    if not destaques_cursos:
        destaques_cursos = [
            {'titulo': c.titulo, 'status': c.status, 'total_visualizacoes': 0}
            for c in Curso.objects.filter(status='publicado')[:5]
        ]

    proximos_eventos = Evento.objects.filter(data__gte=agora).order_by('data')[:3]
    destaques_eventos = EventoSerializer(proximos_eventos, many=True).data

    leituras_eventos = (
        EventoLeitura.objects
        .values('evento__titulo')
        .annotate(
            usuarios=Count('usuario', distinct=True),
            leituras=Count('id'),
        )
        .order_by('-usuarios', '-leituras')[:10]
    )
    leituras_por_evento = [
        {'evento': item['evento__titulo'], 'usuarios': item['usuarios'], 'leituras': item['leituras']}
        for item in leituras_eventos
    ]
    eventos_leituras = {
        'por_evento': leituras_por_evento,
        'total_usuarios': EventoLeitura.objects.values('usuario').distinct().count(),
        'total_leituras': EventoLeitura.objects.count(),
    }

    top_trilhas = Trilha.objects.annotate(
        total_cursos=Count('cursos')
    ).order_by('-total_cursos')[:5]
    destaques_trilhas = [
        {'nome': t.nome, 'ambiente': t.ambiente.nome if t.ambiente else '', 'total_cursos': t.total_cursos}
        for t in top_trilhas
    ]

    alertas = []
    cursos_rascunho = Curso.objects.filter(status='rascunho').count()
    if cursos_rascunho > 0:
        alertas.append({
            'tipo': 'warning',
            'mensagem': f'{cursos_rascunho} curso(s) em rascunho aguardando publicação',
        })

    cursos_sem_descricao = Curso.objects.filter(Q(descricao='') | Q(descricao__isnull=True)).count()
    if cursos_sem_descricao > 0:
        alertas.append({
            'tipo': 'info',
            'mensagem': f'{cursos_sem_descricao} curso(s) sem descrição',
        })

    eventos_proximos = Evento.objects.filter(data__gte=agora, data__lte=trinta_dias_atras).count()
    if eventos_proximos == 0:
        alertas.append({
            'tipo': 'info',
            'mensagem': 'Nenhum evento cadastrado nos próximos 30 dias',
        })

    usuarios_inativos = User.objects.filter(is_active=False).count()
    if usuarios_inativos > 0:
        alertas.append({
            'tipo': 'warning',
            'mensagem': f'{usuarios_inativos} usuário(s) inativo(s)',
        })

    data = {
        'metricas': metricas,
        'crescimento_usuarios': crescimento,
        'eventos_leituras': eventos_leituras,
        'ultimas_atividades': ultimas_atividades,
        'destaques': {
            'top_cursos': destaques_cursos,
            'proximos_eventos': destaques_eventos,
            'top_trilhas': destaques_trilhas,
        },
        'alertas': alertas,
    }
    cache.set(cache_key, data, 120)  # 120 segundos
    return Response(data)

dashboard_stats.throttle_scope = 'dashboard'
dashboard_stats.throttle_classes = [ScopedRateThrottle]


@staff_member_required
@require_POST
def admin_backup_database(request):
    try:
        import importlib.util
        from pathlib import Path
        BASE_DIR = Path(settings.BASE_DIR)
        spec = importlib.util.spec_from_file_location('backup_db', BASE_DIR / 'scripts' / 'backup_db.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        path = mod.backup_postgres()
        messages.success(request, f'Backup criado: {path}')
    except Exception as e:
        messages.error(request, f'Falha no backup: {e}')
    return redirect('admin:index')


@staff_member_required
@require_POST
def admin_restore_database(request):
    try:
        import importlib.util
        from pathlib import Path
        BASE_DIR = Path(settings.BASE_DIR)
        spec = importlib.util.spec_from_file_location('restore_db', BASE_DIR / 'scripts' / 'restore_db.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.restore_latest()
        messages.success(request, 'Restauração concluída.')
    except Exception as e:
        messages.error(request, f'Falha na restauração: {e}')
    return redirect('admin:index')


class ModuloViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ModuloSerializer
    permission_classes = [IsStaffOrReadOnly]

    def get_queryset(self):
        qs = Modulo.objects.select_related('curso').prefetch_related('materiais')
        curso_slug = self.request.query_params.get('curso')
        if curso_slug:
            qs = qs.filter(curso__slug=curso_slug)
        return qs

    def list(self, request, *args, **kwargs):
        curso_slug = request.query_params.get('curso')
        if not curso_slug:
            return Response(
                {'detail': 'O parâmetro "curso" é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            curso = Curso.objects.get(slug=curso_slug)
        except Curso.DoesNotExist:
            return Response(
                {'detail': 'Curso não encontrado.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not user_can_access_curso(curso, request.user):
            return Response(
                {'detail': 'Você não tem permissão para acessar este curso.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        modulos = self.get_queryset()
        serializer = self.get_serializer(modulos, many=True)
        return Response({
            'curso': CursoSerializer(curso, context={'request': request}).data,
            'modulos': serializer.data
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def curso_modulos(request, slug):
    """Retorna módulos e materiais de um curso pelo slug"""
    try:
        curso = Curso.objects.get(slug=slug)
    except Curso.DoesNotExist:
        return Response(
            {'detail': 'Curso não encontrado.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if not user_can_access_curso(curso, request.user):
        return Response(
            {'detail': 'Você não tem permissão para acessar este curso.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    modulos = Modulo.objects.filter(curso=curso, ativo=True).order_by('ordem').prefetch_related('materiais')
    modulos_data = ModuloSerializer(modulos, many=True, context={'request': request}).data
    
    # Vídeos vinculados ao curso
    videos_diretos = Video.objects.filter(curso=curso, ativo=True).order_by('ordem')
    videos_por_modulo = {}
    for v in videos_diretos:
        mid = v.modulo_id if v.modulo_id else 0
        videos_por_modulo.setdefault(mid, []).append(v)

    if modulos.exists():
        # Adiciona vídeos ao módulo correspondente
        for md in modulos_data:
            mid = md['id']
            vids = videos_por_modulo.pop(mid, [])
            if vids:
                materiais_video = []
                for v in vids:
                    arquivo_url = None
                    if v.arquivo:
                        arquivo_url = request.build_absolute_uri(v.arquivo.url) if request else v.arquivo.url
                    materiais_video.append({
                        'id': v.id, 'titulo': v.titulo, 'arquivo': None,
                        'arquivo_url': arquivo_url, 'url_externa': v.url_externa,
                        'modalidade': 'video', 'ordem': v.ordem, 'ativo': v.ativo,
                    })
                md['materiais'] = materiais_video + md.get('materiais', [])
        # Vídeos sem módulo vão para o primeiro módulo
        vids_sem_modulo = videos_por_modulo.pop(0, [])
        if vids_sem_modulo and modulos_data:
            materiais_video = []
            for v in vids_sem_modulo:
                arquivo_url = None
                if v.arquivo:
                    arquivo_url = request.build_absolute_uri(v.arquivo.url) if request else v.arquivo.url
                materiais_video.append({
                    'id': v.id, 'titulo': v.titulo, 'arquivo': None,
                    'arquivo_url': arquivo_url, 'url_externa': v.url_externa,
                    'modalidade': 'video', 'ordem': v.ordem, 'ativo': v.ativo,
                })
            modulos_data[0]['materiais'] = materiais_video + modulos_data[0].get('materiais', [])
    else:
        # Sem módulos — cria módulo virtual com todos os vídeos
        materiais_video = []
        for v in videos_diretos:
            arquivo_url = None
            if v.arquivo:
                arquivo_url = request.build_absolute_uri(v.arquivo.url) if request else v.arquivo.url
            materiais_video.append({
                'id': v.id, 'titulo': v.titulo, 'arquivo': None,
                'arquivo_url': arquivo_url, 'url_externa': v.url_externa,
                'modalidade': 'video', 'ordem': v.ordem, 'ativo': v.ativo,
            })
        modulos_data = [{
            'id': 0, 'curso': curso.id, 'curso_titulo': curso.titulo,
            'titulo': 'Aulas do Curso', 'descricao': '',
            'ordem': 0, 'ativo': True, 'materiais': materiais_video,
        }]
    
    return Response({
        'curso': CursoSerializer(curso, context={'request': request}).data,
        'modulos': modulos_data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def modulo_materiais(request, pk):
    """Retorna materiais de um módulo específico"""
    try:
        modulo = Modulo.objects.select_related('curso').get(pk=pk)
    except Modulo.DoesNotExist:
        return Response(
            {'detail': 'Módulo não encontrado.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if not user_can_access_curso(modulo.curso, request.user):
        return Response(
            {'detail': 'Você não tem permissão para acessar este módulo.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    materiais = modulo.materiais.filter(ativo=True).order_by('ordem')
    serializer = MaterialSerializer(materiais, many=True, context={'request': request})
    return Response({
        'modulo': ModuloSerializer(modulo, context={'request': request}).data,
        'materiais': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_permissions(request):
    user = request.user
    role = get_user_role(user)
    academias = get_academias_permitidas(user)

    links = []
    for academia in academias:
        cursos_count = Curso.objects.filter(ambiente=academia, status='publicado').count()
        links.append({
            'nome': academia.nome,
            'url': f'/frontend/academy-{academia.nome.lower().replace(" ", "-")}/index.html',
            'roles_permitidas': [role],
            'cursos_count': cursos_count,
        })

    total_cursos = 0
    for academia in academias:
        total_cursos += Curso.objects.filter(ambiente=academia, status='publicado').count()

    return Response({
        'role': role,
        'nome_usuario': user.first_name or user.username,
        'academias_permitidas': [a.nome for a in academias],
        'links': links,
        'total_cursos_disponiveis': total_cursos,
    })


from io import BytesIO
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER


@api_view(['GET'])
@permission_classes([AllowAny])
def cursos_recomendados(request):
    from django.db.models import Prefetch
    ambiente_id = request.query_params.get('ambiente')
    user = request.user if request.user.is_authenticated else None
    qs = Curso.objects.filter(is_recomendado=True, status='publicado')
    if ambiente_id:
        qs = qs.filter(Q(ambiente_id=ambiente_id) | Q(academias_extras__id=ambiente_id))
    if user:
        qs = qs.prefetch_related(
            Prefetch(
                'matriculas',
                queryset=Matricula.objects.filter(usuario=user),
                to_attr='_matricula_usuario'
            )
        )
    else:
        qs = qs.prefetch_related(
            Prefetch(
                'matriculas',
                queryset=Matricula.objects.none(),
                to_attr='_matricula_usuario'
            )
        )
    qs = qs.distinct()[:5]
    serializer = CursoSerializer(qs, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def busca(request):
    query = request.query_params.get('q', '').strip()
    if len(query) < 2:
        return Response({'cursos': [], 'modulos': [], 'materiais': []})

    q = query.lower()
    user = request.user if request.user.is_authenticated else None

    cursos_results = Curso.objects.filter(
        Q(titulo__icontains=q) | Q(descricao__icontains=q),
        status='publicado'
    )
    if user and not (user.is_staff or (hasattr(user, 'perfil') and user.perfil.role in ['admin', 'gestor_orcoma'])):
        cursos_ids = [c.id for c in cursos_results if user_can_access_curso(c, user)]
        cursos_results = Curso.objects.filter(id__in=cursos_ids)

    cursos_data = []
    for c in cursos_results[:10]:
        cursos_data.append({
            'id': c.id,
            'titulo': c.titulo,
            'slug': c.slug,
            'descricao': c.descricao[:150] if c.descricao else '',
            'url': f'/frontend/curso/index.html?curso={c.slug}',
            'tipo': 'curso'
        })

    modulos_results = Modulo.objects.filter(
        Q(titulo__icontains=q) | Q(descricao__icontains=q),
        ativo=True,
        curso__status='publicado'
    ).select_related('curso')[:10]

    modulos_data = []
    for m in modulos_results:
        if user and not user_can_access_curso(m.curso, user):
            continue
        modulos_data.append({
            'id': m.id,
            'titulo': m.titulo,
            'curso_titulo': m.curso.titulo,
            'curso_slug': m.curso.slug,
            'url': f'/frontend/curso/index.html?curso={m.curso.slug}&modulo={m.id}',
            'tipo': 'modulo'
        })

    materiais_results = Material.objects.filter(
        Q(titulo__icontains=q),
        ativo=True,
        modulo__curso__status='publicado'
    ).select_related('modulo', 'modulo__curso')[:10]

    materiais_data = []
    for mat in materiais_results:
        if user and not user_can_access_curso(mat.modulo.curso, user):
            continue
        materiais_data.append({
            'id': mat.id,
            'titulo': mat.titulo,
            'curso_titulo': mat.modulo.curso.titulo,
            'modulo_titulo': mat.modulo.titulo,
            'modalidade': mat.modalidade,
            'url': f'/frontend/curso/index.html?curso={mat.modulo.curso.slug}&modulo={mat.modulo.id}',
            'tipo': 'material'
        })

    return Response({
        'cursos': cursos_data,
        'modulos': modulos_data,
        'materiais': materiais_data
    })


def gerar_pdf_certificado(certificado):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    
    styles = getSampleStyleSheet()
    
    title_style = styles['Title']
    title_style.fontName = 'Helvetica-Bold'
    title_style.fontSize = 28
    title_style.textColor = HexColor('#FF9D00')
    title_style.alignment = TA_CENTER
    
    subtitle_style = styles['Heading2']
    subtitle_style.fontName = 'Helvetica'
    subtitle_style.fontSize = 14
    subtitle_style.textColor = HexColor('#333333')
    subtitle_style.alignment = TA_CENTER
    
    normal_style = styles['Normal']
    normal_style.fontName = 'Helvetica'
    normal_style.fontSize = 12
    normal_style.alignment = TA_CENTER
    
    content = []
    
    content.append(Spacer(1, 2*cm))
    content.append(Paragraph('CERTIFICADO', title_style))
    content.append(Spacer(1, 1*cm))
    content.append(Paragraph('Certificamos que', subtitle_style))
    content.append(Spacer(1, 0.5*cm))
    
    name_style = styles['Heading1']
    name_style.fontName = 'Helvetica-Bold'
    name_style.fontSize = 22
    name_style.textColor = HexColor('#1a1a2e')
    name_style.alignment = TA_CENTER
    # Get student name from matricula
    aluno = certificado.matricula.usuario
    aluno_nome = aluno.get_full_name() or aluno.username
    content.append(Paragraph(aluno_nome, name_style))
    
    content.append(Spacer(1, 1*cm))
    content.append(Paragraph('concluiu com êxito o curso', subtitle_style))
    content.append(Spacer(1, 0.5*cm))
    
    course_style = styles['Heading2']
    course_style.fontName = 'Helvetica-Bold'
    course_style.fontSize = 18
    course_style.textColor = HexColor('#FF9D00')
    course_style.alignment = TA_CENTER
    content.append(Paragraph(certificado.matricula.curso.titulo, course_style))
    
    content.append(Spacer(1, 1.5*cm))
    
    data_emissao = certificado.emitido_em.strftime('%d/%m/%Y')
    content.append(Paragraph(f'Emitido em: {data_emissao}', normal_style))
    content.append(Spacer(1, 0.3*cm))
    content.append(Paragraph(f'Código de validação: {certificado.codigo}', normal_style))
    content.append(Spacer(1, 2*cm))
    
    footer_style = styles['Normal']
    footer_style.fontName = 'Helvetica'
    footer_style.fontSize = 10
    footer_style.textColor = HexColor('#666666')
    footer_style.alignment = TA_CENTER
    content.append(Paragraph('Orcoma Academy — https://academy.orcoma.com.br', footer_style))
    
    doc.build(content)
    buffer.seek(0)
    return buffer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_certificados(request):
    certificados = Certificado.objects.filter(matricula__usuario=request.user)
    serializer = CertificadoSerializer(certificados, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_certificado(request, pk):
    try:
        certificado = Certificado.objects.get(pk=pk, matricula__usuario=request.user)
    except Certificado.DoesNotExist:
        return Response({'detail': 'Certificado não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    
    buffer = gerar_pdf_certificado(certificado)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f'certificado_{certificado.codigo}.pdf'
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_stats(request):
    user = request.user
    now = timezone.now()
    academia = request.query_params.get('academia')

    matriculas_qs = Matricula.objects.filter(usuario=user)
    if academia:
        matriculas_qs = matriculas_qs.filter(curso__ambiente__nome=academia)

    total_segundos = matriculas_qs.aggregate(
        total=models.Sum('tempo_total_assistido')
    )['total'] or 0
    horas_estudo = round(total_segundos / 3600, 1) if total_segundos else 0

    total_certificados = Certificado.objects.filter(matricula__usuario=user).count()
    total_concluidos = Matricula.objects.filter(usuario=user, concluido=True).count()
    if academia:
        total_concluidos = Matricula.objects.filter(usuario=user, concluido=True, curso__ambiente__nome=academia).count()

    total_meta_segundos = total_segundos

    today = now.date()
    inicio_semana = today - timedelta(days=today.weekday())
    fim_semana = inicio_semana + timedelta(days=6)
    meta = MetaSemanal.objects.filter(
        usuario=user,
        semana_inicio=inicio_semana,
        semana_fim=fim_semana,
    ).first()

    meta_data = None
    if meta:
        horas_concluidas_calc = round((total_meta_segundos - meta.baseline_tempo) / 3600, 1)
        if horas_concluidas_calc != meta.horas_concluidas:
            MetaSemanal.objects.filter(pk=meta.pk).update(horas_concluidas=horas_concluidas_calc)
            meta.refresh_from_db()
        meta_data = {
            'titulo': meta.titulo,
            'meta_horas': meta.meta_horas,
            'horas_concluidas': meta.horas_concluidas,
            'percentual': meta.percentual,
        }

    return Response({
        'horas_estudo': horas_estudo,
        'total_certificados': total_certificados,
        'total_concluidos': total_concluidos,
        'meta_semanal': meta_data,
    })


# Avaliações de módulos
@api_view(['GET'])
@permission_classes([AllowAny])
def modulo_avaliacoes(request, pk):
    """Retorna avaliações de um módulo específico"""
    try:
        modulo = Modulo.objects.select_related('curso').get(pk=pk)
    except Modulo.DoesNotExist:
        return Response(
            {'detail': 'Módulo não encontrado.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if not user_can_access_curso(modulo.curso, request.user):
        return Response(
            {'detail': 'Você não tem permissão para acessar este módulo.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    avaliacoes = Avaliacao.objects.filter(modulo=pk).order_by('-created_at').select_related('usuario')
    serializer = AvaliacaoSerializer(avaliacoes, many=True, context={'request': request})
    return Response({'results': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def modulo_avaliar(request, pk):
    """Cria uma avaliação para um módulo específico"""
    try:
        modulo = Modulo.objects.select_related('curso').get(pk=pk)
    except Modulo.DoesNotExist:
        return Response(
            {'detail': 'Módulo não encontrado.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if not user_can_access_curso(modulo.curso, request.user):
        return Response(
            {'detail': 'Você não tem permissão para acessar este módulo.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = AvaliacaoSerializer(data={
        'modulo': pk,
        'nota': request.data.get('nota'),
        'comentario': request.data.get('comentario', ''),
    }, context={'request': request})
    
    if serializer.is_valid():
        serializer.save(usuario=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
def modulo_comentarios(request, pk):
    """Lista e cria comentários de um módulo específico"""
    try:
        modulo = Modulo.objects.select_related('curso').get(pk=pk)
    except Modulo.DoesNotExist:
        return Response(
            {'detail': 'Módulo não encontrado.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not user_can_access_curso(modulo.curso, request.user):
        return Response(
            {'detail': 'Você não tem permissão para acessar este módulo.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'GET':
        comentarios = Comentario.objects.filter(
            modulo=pk, comentario_pai__isnull=True
        ).order_by('-created_at').select_related('usuario').prefetch_related('curtido_por')
        serializer = ComentarioSerializer(comentarios, many=True, context={'request': request})
        return Response({'results': serializer.data})

    if not request.user.is_authenticated:
        return Response(
            {'detail': 'Autenticação necessária para comentar.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    serializer = ComentarioSerializer(data={
        'modulo': pk,
        'texto': request.data.get('texto'),
        'comentario_pai': request.data.get('comentario_pai'),
    }, context={'request': request})

    if serializer.is_valid():
        serializer.save(usuario=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def comentario_detail(request, pk):
    """Exclui um comentário (somente o autor ou staff)"""
    try:
        comentario = Comentario.objects.get(pk=pk)
    except Comentario.DoesNotExist:
        return Response(
            {'detail': 'Comentário não encontrado.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if comentario.usuario != request.user and not (request.user.is_superuser or request.user.is_staff):
        return Response(
            {'detail': 'Você não tem permissão para excluir este comentário.'},
            status=status.HTTP_403_FORBIDDEN
        )

    comentario.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def curtir_comentario(request, pk):
    """Curtir/descurtir um comentário"""
    try:
        comentario = Comentario.objects.get(pk=pk)
    except Comentario.DoesNotExist:
        return Response(
            {'detail': 'Comentário não encontrado.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if comentario.curtido_por.filter(pk=request.user.pk).exists():
        comentario.curtido_por.remove(request.user)
        curtido = False
    else:
        comentario.curtido_por.add(request.user)
        curtido = True

    return Response({
        'curtidas': comentario.curtido_por.count(),
        'curtido_por_mim': curtido,
    })

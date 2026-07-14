from rest_framework import viewsets, permissions, generics, status
from .models import Curso, Trilha, Evento, Novidade, LogAtividade, CursoVisualizacao, Matricula, FormacaoAcademica, Habilidade, AssinaturaPlano, Ambiente
from core.services.acesso import filtrar_cursos_acessiveis, user_can_access_curso, get_academias_permitidas
from .serializers import (
    CursoSerializer, TrilhaSerializer, TrilhaListSerializer,
    EventoSerializer, NovidadeSerializer, LogAtividadeSerializer,
    RegisterSerializer, MeSerializer, CustomTokenObtainPairSerializer,
    MatriculaSerializer, MatriculaCreateSerializer,
    FormacaoAcademicaSerializer, HabilidadeSerializer,
    AssinaturaPlanoSerializer
)
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from django.db import connection
from django.utils import timezone
from datetime import timedelta
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.throttling import ScopedRateThrottle


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_staff


class CursoViewSet(viewsets.ModelViewSet):
    serializer_class = CursoSerializer
    permission_classes = [IsStaffOrReadOnly]

    def get_queryset(self):
        qs = Curso.objects.select_related('ambiente').prefetch_related('videos', 'academias_extras')
        user = self.request.user

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
            qs = Curso.objects.select_related('ambiente').prefetch_related('videos', 'academias_extras')
            qs = qs.filter(status=status_param)
            if ambiente:
                qs = qs.filter(
                    Q(ambiente__nome__iexact=ambiente) | Q(ambiente__id=ambiente)
                )

        return qs.distinct()

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


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_scope = 'login'


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    throttle_scope = 'registro'


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user


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


from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
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
        return JsonResponse({'erro': 'API key não configurada'}, status=500)

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
        'usuarios_ativos_7d': User.objects.filter(is_active=True).count(),
    }

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

    return Response({
        'metricas': metricas,
        'crescimento_usuarios': crescimento,
        'ultimas_atividades': ultimas_atividades,
        'destaques': {
            'top_cursos': destaques_cursos,
            'proximos_eventos': destaques_eventos,
            'top_trilhas': destaques_trilhas,
        },
        'alertas': alertas,
    })

dashboard_stats.throttle_scope = 'dashboard'


class AssinaturaPlanoViewSet(viewsets.ModelViewSet):
    serializer_class = AssinaturaPlanoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AssinaturaPlano.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class AdminAssinaturaListView(generics.ListAPIView):
    serializer_class = AssinaturaPlanoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return AssinaturaPlano.objects.select_related('usuario', 'plano').all()
        return AssinaturaPlano.objects.filter(usuario=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if request.user.is_staff:
            for item, obj in zip(data, queryset):
                item['usuario'] = obj.usuario.get_full_name() or obj.usuario.username
        return Response(data)

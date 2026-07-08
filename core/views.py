from rest_framework import viewsets, permissions, generics, status
from .models import Curso, Trilha, Evento, Novidade, LogAtividade, CursoVisualizacao, Matricula
from .serializers import (
    CursoSerializer, TrilhaSerializer, TrilhaListSerializer,
    EventoSerializer, NovidadeSerializer, LogAtividadeSerializer,
    RegisterSerializer, MeSerializer, CustomTokenObtainPairSerializer
)
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.throttling import ScopedRateThrottle


class CursoViewSet(viewsets.ModelViewSet):
    queryset = Curso.objects.all()
    serializer_class = CursoSerializer

    def get_permissions(self):
        if self.action == 'list' or self.action == 'retrieve':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.throttle_scope = 'escrita'
        return super().get_throttles()


class TrilhaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Trilha.objects.all()

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

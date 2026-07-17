from rest_framework import viewsets, permissions, generics, status
from .models import Curso, Trilha, Evento, Novidade, LogAtividade, CursoVisualizacao, Matricula, FormacaoAcademica, Habilidade, AssinaturaPlano, Ambiente, Modulo, Material, Certificado
from core.services.acesso import filtrar_cursos_acessiveis, user_can_access_curso, get_academias_permitidas, get_user_role, get_academias_permitidas_para_role
from .serializers import (
    CursoSerializer, TrilhaSerializer, TrilhaListSerializer,
    EventoSerializer, NovidadeSerializer, LogAtividadeSerializer,
    RegisterSerializer, MeSerializer, CustomTokenObtainPairSerializer,
    MatriculaSerializer, MatriculaCreateSerializer,
    FormacaoAcademicaSerializer, HabilidadeSerializer,
    AssinaturaPlanoSerializer, ModuloSerializer, MaterialSerializer,
    CertificadoSerializer
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


@api_view(['GET'])
@permission_classes([AllowAny])
def ping(request):
    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


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

        Certificado.objects.get_or_create(matricula=matricula)

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
    
    # Verifica se o curso tem vídeos diretos (model Video) que não estão em módulos
    videos_diretos = curso.videos.filter(ativo=True).order_by('ordem')
    
    if videos_diretos.exists():
        # Converte vídeos para o formato de material
        materiais_video = []
        for v in videos_diretos:
            arquivo_url = None
            if v.arquivo:
                if request:
                    arquivo_url = request.build_absolute_uri(v.arquivo.url)
                else:
                    arquivo_url = v.arquivo.url
            
            materiais_video.append({
                'id': v.id,
                'titulo': v.titulo,
                'arquivo': None,
                'arquivo_url': arquivo_url,
                'url_externa': v.url_externa,
                'modalidade': 'video',
                'ordem': v.ordem,
                'ativo': v.ativo,
            })
        
        if modulos.exists():
            # Adiciona os vídeos como materiais no primeiro módulo
            if modulos_data:
                modulos_data[0]['materiais'] = materiais_video + modulos_data[0].get('materiais', [])
        else:
            # Cria um módulo virtual com os vídeos
            modulos_data = [{
                'id': 0,
                'curso': curso.id,
                'curso_titulo': curso.titulo,
                'titulo': 'Aulas do Curso',
                'descricao': '',
                'ordem': 0,
                'ativo': True,
                'materiais': materiais_video,
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
    ambiente_id = request.query_params.get('ambiente')
    qs = Curso.objects.filter(is_recomendado=True, status='publicado')
    if ambiente_id:
        qs = qs.filter(Q(ambiente_id=ambiente_id) | Q(academias_extras__id=ambiente_id))
    qs = qs.distinct()[:5]
    user = request.user if request.user.is_authenticated else None
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
    content.append(Paragraph(certificado.aluno_nome, name_style))
    
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

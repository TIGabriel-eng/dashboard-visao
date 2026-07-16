from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'cursos', views.CursoViewSet, basename='curso')
router.register(r'modulos', views.ModuloViewSet, basename='modulo')
router.register(r'trilhas', views.TrilhaViewSet, basename='trilha')
router.register(r'eventos', views.EventoViewSet, basename='evento')
router.register(r'novidades', views.NovidadeViewSet, basename='novidade')
router.register(r'logs', views.LogAtividadeViewSet, basename='log')
router.register(r'matriculas', views.MatriculaViewSet, basename='matricula')
router.register(r'formacoes', views.FormacaoAcademicaViewSet, basename='formacao')
router.register(r'habilidades', views.HabilidadeViewSet, basename='habilidade')
router.register(r'assinaturas', views.AssinaturaPlanoViewSet, basename='assinatura')

urlpatterns = [
    path('', include(router.urls)),
    path('ping/', views.ping, name='ping'),
    path('dashboard/', views.dashboard_stats, name='dashboard-stats'),
    path('dashboard-data/', views.dashboard_stats, name='dashboard-data'),
    path('corrigir-texto/', views.corrigir_texto, name='corrigir-texto'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('me/', views.MeView.as_view(), name='me'),
    path('admin-assinaturas/', views.AdminAssinaturaListView.as_view(), name='admin-assinaturas'),
    path('user-permissions/', views.user_permissions, name='user-permissions'),
    path('cursos/<slug:slug>/modulos/', views.curso_modulos, name='curso-modulos'),
    path('modulos/<int:pk>/materiais/', views.modulo_materiais, name='modulo-materiais'),
    path('certificados/', views.listar_certificados, name='listar-certificados'),
    path('certificados/<int:pk>/download/', views.download_certificado, name='download-certificado'),
    path('busca/', views.busca, name='busca'),
]

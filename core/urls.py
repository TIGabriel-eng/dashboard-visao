from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'cursos', views.CursoViewSet, basename='curso')
router.register(r'trilhas', views.TrilhaViewSet, basename='trilha')
router.register(r'eventos', views.EventoViewSet, basename='evento')
router.register(r'novidades', views.NovidadeViewSet, basename='novidade')
router.register(r'logs', views.LogAtividadeViewSet, basename='log')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', views.dashboard_stats, name='dashboard-stats'),
    path('dashboard-data/', views.dashboard_stats, name='dashboard-data'),
    path('corrigir-texto/', views.corrigir_texto, name='corrigir-texto'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('me/', views.MeView.as_view(), name='me'),
]

"""
Sistema de tracking de progresso para importação em massa.
Usa Django Cache para armazenar o progresso em tempo real.
"""
from django.core.cache import cache
import time


def gerar_import_id():
    """Gera um ID único para cada importação"""
    return f"import_{int(time.time())}"


def iniciar_importacao(total_usuarios):
    """
    Inicia o tracking de uma importação.
    Retorna o import_id para ser usado nas requisições de progresso.
    """
    import_id = gerar_import_id()
    cache.set(import_id, {
        'status': 'processing',
        'total': total_usuarios,
        'processados': 0,
        'sucessos': 0,
        'erros': 0,
        'novos_usuarios': [],
        'inicio': time.time(),
    }, timeout=3600)  # 1 hora de timeout
    return import_id


def atualizar_progresso(import_id, processados, sucessos, erros, novos_usuarios=None):
    """Atualiza o progresso da importação"""
    dados = cache.get(import_id)
    if dados:
        dados['processados'] = processados
        dados['sucessos'] = sucessos
        dados['erros'] = erros
        if novos_usuarios:
            dados['novos_usuarios'].extend(novos_usuarios)
        cache.set(import_id, dados, timeout=3600)


def finalizar_importacao(import_id, status='completed', error=None):
    """Marca a importação como concluída ou com erro"""
    dados = cache.get(import_id)
    if dados:
        dados['status'] = status
        if error:
            dados['error'] = error
        dados['fim'] = time.time()
        cache.set(import_id, dados, timeout=3600)


def obter_progresso(import_id):
    """Retorna o progresso atual da importação"""
    return cache.get(import_id)


def limpar_progresso(import_id):
    """Remove o progresso do cache"""
    cache.delete(import_id)
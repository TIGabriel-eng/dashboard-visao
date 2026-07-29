"""
Serviço de importação assíncrona com tracking de progresso.
Executa a importação em thread separada e atualiza o progresso em tempo real.
"""
import logging
import threading
import os
import traceback
from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile

from core.services.importacao import processar_arquivo_excel
from core.services.progresso_importacao import (
    atualizar_progresso,
    finalizar_importacao,
    obter_progresso,
)

logger = logging.getLogger(__name__)


def importar_usuarios_async(arquivo_path, import_id):
    """
    Executa a importação em thread separada.
    Atualiza o progresso no cache para ser exibido em tempo real.
    """
    import django
    django.db.close_old_connections()

    try:
        logger.info(f"[Thread {import_id}] Iniciando importação assíncrona...")

        with open(arquivo_path, 'rb') as f:
            arquivo_bytes = f.read()
        logger.info(f"[Thread {import_id}] Arquivo lido: {len(arquivo_bytes)} bytes")

        arquivo = InMemoryUploadedFile(
            BytesIO(arquivo_bytes),
            'file',
            'import.xlsx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            len(arquivo_bytes),
            None
        )

        def progresso_callback(processados, sucessos, erros):
            atualizar_progresso(
                import_id=import_id,
                processados=processados,
                sucessos=sucessos,
                erros=erros,
                novos_usuarios=[],
            )
            logger.info(
                f"[Thread {import_id}] Progresso: {processados} processados, "
                f"{sucessos} sucessos, {erros} erros"
            )

        resultado, erro = processar_arquivo_excel(
            arquivo, criar_usuarios=True, progress_callback=progresso_callback,
        )

        if erro:
            logger.error(f"[Thread {import_id}] Erro de validação: {erro}")
            finalizar_importacao(import_id, status='error', error=str(erro))
            return

        logger.info(
            f"[Thread {import_id}] Processado: {resultado['total_processado']} "
            f"(sucessos={resultado['sucessos']}, erros={resultado['total_erros']})"
        )

        atualizar_progresso(
            import_id=import_id,
            processados=resultado['total_processado'],
            sucessos=resultado['sucessos'],
            erros=resultado['total_erros'],
            novos_usuarios=[
                {'username': u['username'], 'email': u['email']}
                for u in resultado['usuarios'][:50]
            ]
        )

        finalizar_importacao(import_id, status='completed')
        logger.info(f"[Thread {import_id}] Importação concluída com sucesso!")

    except Exception as e:
        erro_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        logger.error(f"[Thread {import_id}] Exceção: {erro_msg}")
        print(f"[ERRO THREAD {import_id}] {erro_msg}")
        finalizar_importacao(import_id, status='error', error=str(e))
    finally:
        try:
            os.unlink(arquivo_path)
        except:
            pass
"""
Script de Keep Alive para o vISÃO Academy.
Mantém o backend do Render acordado fazendo pings periódicos.

Uso local:   python keep_alive.py
Uso no cron: configurado no render.yaml (a cada 5 min)

Recomendação: Use também o UptimeRobot (gratuito) para monitoramento externo:
  1. Crie uma conta em https://uptimerobot.com
  2. Adicione um monitor HTTP(s) apontando para:
     https://orcoma-academy-backend.onrender.com/api/ping/
  3. Intervalo: 5 minutos
  4. Isso mantém o backend acordado 24h mesmo se o cron do Render falhar
"""

import os
import sys
import requests
import time

# URLs para pingar (adicione mais se necessário)
# URL principal para ping
# O Render free dorme após 15 min sem atividade
# O ping periódico mantém o servidor acordado
DEFAULT_URL = "https://orcoma-academy-backend.onrender.com/api/ping/"

URLS = [
    os.environ.get("APP_URL", DEFAULT_URL),
]

# Remove vazios
URLS = [u for u in URLS if u.strip()]

TIMEOUT = 30  # segundos
RETRY_COUNT = 2
RETRY_DELAY = 5  # segundos entre tentativas


def ping_url(url: str) -> tuple[bool, str]:
    """Tenta pingar uma URL com retry em caso de falha."""
    for attempt in range(1, RETRY_COUNT + 2):
        try:
            response = requests.get(url, timeout=TIMEOUT)
            msg = f"[OK] {response.status_code} - {response.text[:100]}"
            print(msg)
            return True, msg
        except requests.exceptions.ConnectionError as e:
            msg = f"[FALHA] Tentativa {attempt}/{RETRY_COUNT + 1} - Erro de conexão: {e}"
            print(msg)
            if attempt <= RETRY_COUNT:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.Timeout as e:
            msg = f"[FALHA] Tentativa {attempt}/{RETRY_COUNT + 1} - Timeout: {e}"
            print(msg)
            if attempt <= RETRY_COUNT:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.RequestException as e:
            msg = f"[FALHA] Tentativa {attempt}/{RETRY_COUNT + 1} - Erro: {e}"
            print(msg)
            if attempt <= RETRY_COUNT:
                time.sleep(RETRY_DELAY)
    return False, f"Todas as {RETRY_COUNT + 1} tentativas falharam para {url}"


def main():
    print(f"Iniciando Keep Alive - {len(URLS)} URL(s) para pingar:")
    for url in URLS:
        print(f"  - {url}")
    print()

    ALL_SUCCESS = True
    for url in URLS:
        success, msg = ping_url(url)
        if not success:
            ALL_SUCCESS = False
        print()

    if ALL_SUCCESS:
        print("Keep Alive concluído com sucesso!")
        sys.exit(0)
    else:
        print("ALERTA: Alguns pings falharam!")
        sys.exit(1)


if __name__ == "__main__":
    main()
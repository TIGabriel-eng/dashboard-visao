import os
import requests

url = os.environ.get("APP_URL", "http://localhost:8000/api/ping/")

try:
    response = requests.get(url, timeout=30)
    print(f"Ping: {response.status_code} - {response.text}")
except requests.exceptions.RequestException as e:
    print(f"Erro ao fazer ping: {e}")

import requests
from django.conf import settings
from rest_framework.exceptions import ValidationError

RECAPTCHA_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'


def verify_recaptcha_token(token):
    secret = getattr(settings, 'RECAPTCHA_SECRET_KEY', '')
    if not secret:
        return True

    if not token:
        raise ValidationError({'recaptcha': 'Complete o reCAPTCHA para continuar.'})

    try:
        response = requests.post(
            RECAPTCHA_VERIFY_URL,
            data={'secret': secret, 'response': token},
            timeout=5,
        )
        result = response.json()
    except (requests.RequestException, ValueError):
        raise ValidationError({'recaptcha': 'Não foi possível validar o reCAPTCHA. Tente novamente.'})

    if not result.get('success'):
        raise ValidationError({'recaptcha': 'Validação do reCAPTCHA falhou. Tente novamente.'})

    return True

import base64
import os
import logging
import threading
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _enviar_email_resend(params, user_email):
    try:
        import resend
        resend.api_key = os.environ.get('RESEND_API_KEY', '')
        resend.Emails.send(params)
        logger.info('E-mail enviado para %s', user_email)
    except Exception:
        logger.exception('Erro ao enviar e-mail para %s', user_email)


def enviar_email_reset_senha(user, token):
    frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
    reset_url = f'{frontend_url}/redefinir-senha?token={token}'

    html_message = render_to_string('emails/password_reset.html', {
        'user_name': user.first_name or user.username,
        'reset_url': reset_url,
    })
    plain_message = strip_tags(html_message)

    if not os.environ.get('RESEND_API_KEY'):
        logger.warning('RESEND_API_KEY não configurada. Link: %s', reset_url)
        return reset_url

    params = {
        'from': 'Orcoma Academy <noreply@academy.orcomacontabilidade.com.br>',
        'to': [user.email],
        'subject': 'Redefina sua senha - Orcoma Academy',
        'html': html_message,
        'text': plain_message,
    }

    thread = threading.Thread(target=_enviar_email_resend, args=(params, user.email))
    thread.daemon = True
    thread.start()

    return reset_url


SUPORTE_DESTINO = 'timaracas@orcoma.com.br'

_TAGS_PERMITIDAS = {'b', 'strong', 'i', 'em', 'u', 'br', 'p', 'div', 'span', 'ul', 'ol', 'li', 'a'}


class _Sanitizador(HTMLParser):
    """Mantém só formatação básica e links http/https/mailto; descarta o resto (scripts, imagens, estilos)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []
        self._ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self._ignorar += 1
            return
        if tag not in _TAGS_PERMITIDAS or self._ignorar:
            return
        if tag == 'a':
            href = dict(attrs).get('href', '') or ''
            if href.lower().startswith(('http://', 'https://', 'mailto:')):
                self.partes.append(f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">')
            else:
                self.partes.append('<a>')
        else:
            self.partes.append(f'<{tag}>')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._ignorar = max(0, self._ignorar - 1)
            return
        if tag in _TAGS_PERMITIDAS and tag != 'br' and not self._ignorar:
            self.partes.append(f'</{tag}>')

    def handle_data(self, data):
        if not self._ignorar:
            self.partes.append(escape(data))


def sanitizar_html(html):
    s = _Sanitizador()
    s.feed(html or '')
    s.close()
    return ''.join(s.partes)


def enviar_email_suporte(user, assunto, mensagem_html, anexos=None):
    """Envia a mensagem do aluno para a caixa de entrada do suporte.
    anexos: lista de (nome, bytes). O reply_to é o e-mail do aluno, para o suporte responder direto."""
    if not os.environ.get('RESEND_API_KEY'):
        logger.warning('RESEND_API_KEY não configurada. Mensagem de suporte de %s não enviada.', user.email)
        return False

    nome = user.get_full_name() or user.username
    corpo = sanitizar_html(mensagem_html)
    html = (
        f'<p><strong>Aluno:</strong> {escape(nome)} ({escape(user.email)})</p>'
        f'<p><strong>Assunto:</strong> {escape(assunto)}</p>'
        f'<hr><div>{corpo}</div>'
    )
    params = {
        'from': 'Orcoma Academy <noreply@academy.orcomacontabilidade.com.br>',
        'to': [SUPORTE_DESTINO],
        'subject': f'[Suporte Academy] {assunto}',
        'html': html,
        'text': f'Aluno: {nome} ({user.email})\nAssunto: {assunto}\n\n{strip_tags(corpo)}',
    }
    if user.email:
        params['reply_to'] = user.email
    if anexos:
        params['attachments'] = [
            {'filename': n, 'content': base64.b64encode(c).decode('ascii')} for n, c in anexos
        ]

    try:
        import resend
        resend.api_key = os.environ.get('RESEND_API_KEY', '')
        resend.Emails.send(params)
        return True
    except Exception:
        logger.exception('Erro ao enviar e-mail de suporte de %s', user.email)
        return False

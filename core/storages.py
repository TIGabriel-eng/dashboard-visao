"""Backend de armazenamento para o Supabase Storage (compatível com S3).

O Supabase expõe um endpoint S3 (``.../storage/v1/s3``) para upload/listagem e
uma base de URLs públicas (``.../storage/v1/object/public/<bucket>``) para
leitura direta dos arquivos. Esta classe adapta o ``S3Storage`` (django-storages)
a esse modelo.
"""

import re

from django.conf import settings

try:
    from storages.backends.s3 import S3Storage as SupabaseBaseStorage
except ImportError:  # django-storages < 1.14 (backend legado)
    from storages.backends.s3boto3 import S3Boto3Storage as SupabaseBaseStorage


def _public_object_base(endpoint_url, bucket_name):
    """Deriva a base de URLs públicas a partir do endpoint S3 do Supabase.

    Ex.: ``https://projeto.supabase.co/storage/v1/s3`` + bucket ``media``
    -> ``https://projeto.supabase.co/storage/v1/object/public/media``.
    """
    if not endpoint_url or not bucket_name:
        return None
    base = endpoint_url.rstrip('/')
    base = re.sub(r'/storage/v1/s3$', '', base)
    return f"{base}/storage/v1/object/public/{bucket_name}"


class SupabaseS3Storage(SupabaseBaseStorage):
    """``S3Storage`` ajustado para o Supabase Storage.

    Diferenças em relação ao backend S3 padrão:

    * ``default_acl = None`` — não envia ACL no upload (o S3 do Supabase não
      aceita ``x-amz-acl``; o acesso é controlado pela política do bucket no
      painel do Supabase).
    * ``querystring_auth = False`` — gera URLs públicas sem assinatura.
    * ``custom_domain`` resolvido automaticamente para a base pública
      ``/storage/v1/object/public/<bucket>`` (override via
      ``SUPABASE_S3_PUBLIC_URL`` se necessário).
    """

    default_acl = None
    querystring_auth = False

    def get_default_settings(self):
        defaults = super().get_default_settings()
        public_url = (
            getattr(settings, 'SUPABASE_S3_PUBLIC_URL', '')
            or _public_object_base(
                defaults.get('endpoint_url'),
                defaults.get('bucket_name'),
            )
        )
        if public_url:
            # O S3Storage prefixa o custom_domain com o protocolo configurado
            # (AWS_S3_URL_PROTOCOL), então guardamos sem o scheme.
            defaults['custom_domain'] = public_url.rstrip('/').split('://', 1)[-1]
        return defaults
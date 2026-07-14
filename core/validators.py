import os

from django.core.exceptions import ValidationError


VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.m4v'}
VIDEO_MAX_BYTES = 500 * 1024 * 1024  # 500 MB


def validate_video_file(value):
    if not value:
        return
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        raise ValidationError(
            f'Formato não permitido. Use: {", ".join(sorted(VIDEO_EXTENSIONS))}.'
        )
    if value.size > VIDEO_MAX_BYTES:
        raise ValidationError('O vídeo excede o tamanho máximo de 500 MB.')

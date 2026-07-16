import os
from pathlib import Path
from django.conf import settings
from django.db import connection

BACKUP_DIR = Path(settings.BASE_DIR) / 'backups'


def restore_latest():
    backups = sorted(BACKUP_DIR.glob('backup_*.sql'), reverse=True)
    if not backups:
        print('Nenhum backup encontrado')
        return
    path = backups[0]
    sql = path.read_text(encoding='utf-8')
    with connection.cursor() as cursor:
        cursor.execute('BEGIN')
        try:
            cursor.execute(sql)
            cursor.execute('COMMIT')
        except Exception as e:
            cursor.execute('ROLLBACK')
            raise e
    print('Restore em', path)


if __name__ == '__main__':
    restore_latest()
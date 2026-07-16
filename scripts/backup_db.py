import os
import datetime
import dj_database_url
from django.conf import settings
from django.db import connection

BACKUP_DIR = os.path.join(settings.BASE_DIR, 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)


def backup_postgres():
    db = settings.DATABASES['default']
    name = db.get('NAME')
    if not name:
        return None
    filename = f"backup_{name}_{datetime.date.today().isoformat()}.sql"
    path = os.path.join(BACKUP_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        with connection.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            tables = [r[0] for r in cursor.fetchall()]
            for table in tables:
                f.write(f"CREATE TABLE IF NOT EXISTS {table} ();\n")
                cursor.execute(f"SELECT * FROM {table} LIMIT 0")
                cols = [d.name for d in cursor.description]
                cursor.execute(f"SELECT * FROM {table}")
                for row in cursor.fetchall():
                    vals = ', '.join(["'" + str(v).replace("'", "''") + "'" if v is not None else 'NULL' for v in row])
                    f.write(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({vals});\n")
    return path


if __name__ == '__main__':
    p = backup_postgres()
    print('Backup:', p)
# Scripts de persistência do banco de dados

## backup_db.py
Gera backup em SQL do banco PostgreSQL configurado em `DATABASE_URL`.
- Saída: pasta `backups/` no diretório do projeto
- Nome: `backup_{database}_{YYYY-MM-DD}.sql`

Uso local/teste:
```
python manage.py shell < scripts/backup_db.py
# ou, na pasta backend:
python scripts/backup_db.py
```

## restore_db.py
Restaura o backup mais recente dentro de uma transação.
```
python manage.py shell < scripts/restore_db.py
# ou, na pasta backend:
python scripts/restore_db.py
```

## Automatização no Render
Para agendar backups automáticos, adicione ao `render.yaml` um job cron:

```yaml
- type: cron
  name: orcoma-db-backup
  runtime: python
  buildCommand: pip install requests
  schedule: "0 3 * * *"  # diariamente às 03:00 BRT
  startCommand: python scripts/backup_db.py
  envVars:
    - key: DATABASE_URL
      fromDatabase:
        name: orcoma-db
        property: connectionString
```

## Plano de persistência recomendado
- Mude para plano pago do Render para evitar exclusão do banco por inatividade.
- Considere exportar os backups para armazenamento externo.
- Monitore espaço e idade dos backups.
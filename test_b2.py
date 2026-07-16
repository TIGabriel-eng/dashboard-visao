import os
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

import boto3

key_id = os.getenv('AWS_ACCESS_KEY_ID')
secret = os.getenv('AWS_SECRET_ACCESS_KEY')
print(f'KEY ID: {repr(key_id)}')
print(f'SECRET: {repr(secret)}')
print(f'SECRET len: {len(secret) if secret else 0}')

s3 = boto3.client(
    's3',
    endpoint_url='https://s3.us-west-004.backblazeb2.com',
    aws_access_key_id=key_id,
    aws_secret_access_key=secret,
    region_name='us-west-004'
)

try:
    response = s3.list_objects_v2(Bucket='orcoma-media')
    print(f'\nObjetos em orcoma-media: {response.get("KeyCount", 0)}')
    print('Conexao com bucket especifico OK!')
except Exception as e:
    print(f'\nErro ao acessar orcoma-media: {e}')
    print('\nTentando listar buckets disponiveis...')
    try:
        resp = s3.list_buckets()
        print('Buckets encontrados:')
        for b in resp.get('Buckets', []):
            print(f'  - {b["Name"]}')
    except Exception as e2:
        print(f'Erro ao listar buckets: {e2}')

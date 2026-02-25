import duckdb
import os
from api.config import settings

class DatabaseManager:
    """
    Gerencia a conexão com o DuckDB de forma agnóstica ao ambiente.
    Utiliza httpfs para ler diretamente do bucket S3 ou MinIO.
    """
    
    def __init__(self):
        self._conn = None

    def get_connection(self):
        if self._conn is None:
            # Cria uma conexão em memória
            self._conn = duckdb.connect(':memory:')
            
            # Instala e carrega a extensão httpfs para acesso remoto
            self._conn.execute("INSTALL httpfs; LOAD httpfs;")
            
            # Configura credenciais
            self._conn.execute(f"SET s3_access_key_id='{settings.AWS_ACCESS_KEY_ID}';")
            self._conn.execute(f"SET s3_secret_access_key='{settings.AWS_SECRET_ACCESS_KEY}';")
            self._conn.execute(f"SET s3_region='{settings.AWS_REGION}';")
            
            # Configuração agnóstica: MinIO (Endpoint presente) vs S3 Real (Endpoint vazio)
            if settings.S3_ENDPOINT_URL:
                # Local/MinIO
                endpoint = settings.S3_ENDPOINT_URL.replace("http://", "").replace("https://", "")
                self._conn.execute(f"SET s3_endpoint='{endpoint}';")
                self._conn.execute("SET s3_use_ssl=false;")
                self._conn.execute("SET s3_url_style='path';")
            else:
                # AWS S3 Real
                self._conn.execute("SET s3_use_ssl=true;")
                self._conn.execute("SET s3_url_style='vhost';")
            
            # Monta o caminho remoto do banco Ouro
            s3_path = f"s3://{settings.BUCKET_NAME}/{settings.GOLD_PATH}"
            
            # Anexa o arquivo remoto como um banco de dados
            # Usamos prefixo 'gold_db' para isolar as tabelas
            self._conn.execute(f"ATTACH '{s3_path}' AS gold_db (READ_ONLY);")
            
        return self._conn

# Singleton instance
db_manager = DatabaseManager()

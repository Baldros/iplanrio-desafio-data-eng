import duckdb
from config import settings

class DatabaseManager:
    """
    Gerencia a conexão com o DuckDB de forma agnóstica ao ambiente.
    Utiliza httpfs para ler diretamente do bucket S3 ou MinIO.
    """
    
    def __init__(self):
        self._conn = None

    def get_connection(self):
        if self._conn is None:
            # Cria conexão em memória
            self._conn = duckdb.connect(':memory:')
            
            # Garante que as extensões estão prontas
            self._conn.execute("INSTALL httpfs; LOAD httpfs;")
            
            # CONFIGURAÇÃO PROFISSIONAL: DuckDB Secrets (v1.0+)
            # Isso centraliza a configuração do S3 de forma segura e robusta.
            
            # Limpa o endpoint (remove protocolo para o DuckDB)
            endpoint = ""
            if settings.S3_ENDPOINT_URL:
                endpoint = settings.S3_ENDPOINT_URL.replace("http://", "").replace("https://", "")
            
            # Cria o secret dinamicamente
            # Se endpoint estiver vazio, o DuckDB assume AWS S3 oficial.
            secret_cmd = f"""
                CREATE OR REPLACE SECRET s3_creds (
                    TYPE S3,
                    KEY_ID '{settings.AWS_ACCESS_KEY_ID}',
                    SECRET '{settings.AWS_SECRET_ACCESS_KEY}',
                    REGION '{settings.AWS_REGION}',
                    ENDPOINT '{endpoint}',
                    URL_STYLE '{'path' if endpoint else 'vhost'}',
                    USE_SSL {str(not bool(endpoint)).lower()}
                );
            """
            self._conn.execute(secret_cmd)
            
            # Caminho URI S3
            s3_path = f"s3://{settings.BUCKET_NAME}/{settings.GOLD_PATH}"
            
            try:
                # Agora o ATTACH usa automaticamente o secret 's3_creds'
                self._conn.execute(f"ATTACH '{s3_path}' AS gold_db (READ_ONLY);")
                print(f"Suceso: Cloud Mount estabelecido em {s3_path}")
            except Exception as e:
                # Fallback técnico: Se o ATTACH do arquivo .duckdb via S3 falhar (limitação de alguns providers/versões)
                # O ideal em uma arquitetura Data Lakehouse seria ler Parquet, 
                # mas vamos tentar garantir que o erro seja claro.
                raise RuntimeError(f"Erro ao montar banco Ouro via S3 Secrets: {e}")
                
        return self._conn
            
        return self._conn

# Singleton instance
db_manager = DatabaseManager()

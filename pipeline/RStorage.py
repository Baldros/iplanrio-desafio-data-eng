"""
Módulo responsável por fazer o ETL segundo a arquitetura 
Medallion demandada no desafio, usando o DuckDB como
SGBD Relacional.
"""

import os
import duckdb
import subprocess
from dotenv import load_dotenv

load_dotenv()

class DuckDBClient:
    """
    Classe responsável por criar o cliente com o DuckDB.
    Aqui estruturamos toda a comunicação com o DuckDB,
    tanto leitura, quanto escrita.
    """
    
    def __init__(self):
        # Diretório tmp na raiz do projeto
        self.tmp_dir = os.path.join(os.getcwd(), "tmp")
        os.makedirs(self.tmp_dir, exist_ok=True)
        
        # Paths dos arquivos .duckdb por camada
        self.bronze_path = os.path.join(self.tmp_dir, "terceirizados-bronze.duckdb")
        self.silver_path = os.path.join(self.tmp_dir, "terceirizados-silver.duckdb")
        self.gold_path   = os.path.join(self.tmp_dir, "terceirizados-gold.duckdb")
        
        # Credenciais MinIO
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.s3_endpoint   = endpoint.replace("http://", "").replace("https://", "")
        self.s3_access_key = os.getenv("MINIO_ROOT_USER", "")
        self.s3_secret_key = os.getenv("MINIO_ROOT_PASSWORD", "")

    def create_bronze(self, bucket_name: str, prefix: str = "raw/", table_name: str = "terceirizados") -> str:
        """
        Lê todos os Parquets disponíveis no MinIO (camada raw), consolida
        fisicamente num banco de dados DuckDB (.duckdb) local e temporário.
        Retorna o caminho (path) absoluto do arquivo gerado para upload.
        """
        # Garante que o diretório exista se usarmos um path com subdiretórios
        db_dir = os.path.dirname(self.bronze_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        print(f"[DuckDB] Consolidando arquivos do s3://{bucket_name}/{prefix}*.parquet no banco {self.bronze_path}...")
            
        # Conecta ao arquivo físico (se não existir, ele cria)
        conn = duckdb.connect(self.bronze_path)
        
        try:
            # Instala e carrega extensão para ler do S3/MinIO
            conn.execute("INSTALL httpfs;")
            conn.execute("LOAD httpfs;")
            
            # Configura credenciais
            conn.execute(f"SET s3_endpoint='{self.s3_endpoint}';")
            conn.execute(f"SET s3_access_key_id='{self.s3_access_key}';")
            conn.execute(f"SET s3_secret_access_key='{self.s3_secret_key}';")
            
            # Configurações essenciais para MinIO (usar HTTP no dev e path style)
            conn.execute("SET s3_use_ssl=false;")
            conn.execute("SET s3_url_style='path';")
            
            # Cria a tabela consolidando TODOS os parquets usando glob pattern (*)
            query = f"""CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet('s3://{bucket_name}/{prefix}*.parquet', union_by_name=true)"""
            conn.execute(query)
            print(f"[DuckDB] Banco consolidado com sucesso em: {self.bronze_path}")
            
        finally:
            # É crítico fechar a conexão para que todos os bytes sejam descarregados do WAL (Write-Ahead Log)
            # para o arquivo principal .duckdb antes do upload.
            conn.close()

        # Retorna o path físico elegante para ser usado pelo upload_file
        return self.bronze_path

    def create_silver(self, db_dir: str) -> str:
        """
        Gera a camada Silver orquestrando o dbt (Data Build Tool).
        O dbt transformará a origin-table (bronze.duckdb) no modelo target (silver.duckdb).
        - db_dir: Caminho absoluto do diretório contendo o arquivo bronze.duckdb baixado
        """
        print(f"[DuckDB/dbt] Iniciando processo de transformação dbt Silver...")
        
        # Assumindo que o diretório tmp está na raiz do projeto e o dbt no subdiretório dbt/
        # Retrocedemos uma pasta a partir de db_dir (/tmp) para chegar na raiz
        project_root = os.path.dirname(db_dir)
        dbt_project_dir = os.path.join(project_root, "dbt")
        
        try:
            # Executa o comando dbt de forma limpa, já que o profiles.yml usa paths relativos
            result = subprocess.run(
                ["dbt", "run", "--select", "silver", "--target", "silver"],
                cwd=dbt_project_dir,
                check=True,
                capture_output=True,
                text=True
            )
            print("[DuckDB/dbt] Transformação dbt concluída com sucesso!")
            print(result.stdout)
            
        except subprocess.CalledProcessError as e:
            print(f"[DuckDB/dbt] Falha durante a compilação do dbt:\n{e.stderr}")
            raise e

        # Retorna o path do resultado
        return os.path.join(db_dir, "terceirizados-silver.duckdb")

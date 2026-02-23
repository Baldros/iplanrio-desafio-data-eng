import os
import io
from minio import Minio
from dotenv import load_dotenv

load_dotenv()

class MinioClient:
    """
    Classe responsável por abstrair a comunicação com o servidor MinIO (ou AWS S3).
    Lida com a criação de buckets, listagem de objetos e o upload de dados, 
    tanto na forma de objetos em memória (buffers do Polars) quanto arquivos em disco (.duckdb).
    """
    
    def __init__(self):
        # Carrega configurações do .env com fallback para valores padrão locais
        self.endpoint = os.getenv("MINIO_ENDPOINT", "")
        self.access_key = os.getenv("MINIO_ROOT_USER", "")
        self.secret_key = os.getenv("MINIO_ROOT_PASSWORD", "")
        
        # Conexão com o Minio
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=False  # Para dev usamos HTTP local. Em prod seria True.
        )
        
    def ensure_bucket_exists(self, bucket_name: str) -> None:
        """
        Verifica se o bucket existe. Caso não exista, ele será criado.
        """
        if not self.client.bucket_exists(bucket_name):
            self.client.make_bucket(bucket_name)
            #print(f"[MinIO] Bucket '{bucket_name}' criado com sucesso.")
        else:
            #print(f"[MinIO] Bucket '{bucket_name}' já existe.")
            pass

    def upload_buffer(self, bucket_name: str, object_name: str, buffer: io.BytesIO) -> None:
        """
        Faz o upload de um objeto armazenado em memória (BytesIO) para o MinIO.
        - bucket_name: Nome do bucket destino (ex: 'terceirizados')
        - object_name: Caminho completo dentro do bucket (ex: 'raw/terceirizados2025.parquet')
        - buffer: Buffer com os dados carregados na memória RAM.
        """
        # Sempre garantir que o ponteiro do buffer está no início antes do upload
        buffer.seek(0)
        
        self.client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=buffer,
            length=buffer.getbuffer().nbytes,
            content_type="application/octet-stream"
        )
        #print(f"[MinIO] Upload de buffer concluído: s3://{bucket_name}/{object_name}")

    def upload_file(self, bucket_name: str, object_name: str, file_path: str) -> None:
        """
        Faz o upload de um arquivo físico em disco para o MinIO.
        Útil nas etapas de transformação (ex: gravou um 'bronze.duckdb' localmente e quer subir).
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo local não encontrado: {file_path}")
            
        self.client.fput_object(
            bucket_name=bucket_name,
            object_name=object_name,
            file_path=file_path,
        )
        #print(f"[MinIO] Upload de arquivo concluído: s3://{bucket_name}/{object_name}")

    def list_objects(self, bucket_name: str, prefix: str = "") -> list[str]:
        """
        Lista todos os objetos dentro de um bucket com um determinado prefixo.
        Ideal para descobrir quais arquivos já foram processados na arquitetura (idempotência).
        """
        if not self.client.bucket_exists(bucket_name):
            return []
            
        objetos = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objetos]

"""
Módulo responsável por criar o cliente com o Objective Storage. Aqui
estruturamos toda a comunicação com o MinIO (dev) ou AWS S3 (prod),
tanto leitura, quanto escrita.

A troca entre ambientes é feita via variáveis de ambiente:
- Dev (MinIO local): definir S3_ENDPOINT_URL no .env
- Prod (AWS S3):     remover ou deixar S3_ENDPOINT_URL vazio
"""

import os
import io
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


class OBJStorageClient:
    """
    Classe responsável por abstrair a comunicação com o object storage S3-compatível.
    Usa boto3 internamente, o que permite apontar tanto para o MinIO local (dev)
    quanto para o AWS S3 real (prod) apenas trocando variáveis de ambiente.

    Variáveis de ambiente esperadas:
        S3_ENDPOINT_URL      -> URL do MinIO em dev (ex: http://localhost:9000)
                                Deixar vazio ou ausente para usar AWS S3 em prod
        AWS_ACCESS_KEY_ID    -> Access key (MinIO root user em dev)
        AWS_SECRET_ACCESS_KEY-> Secret key (MinIO root password em dev)
        AWS_REGION           -> Região AWS (usado em prod; ignorado pelo MinIO)
    """

    def __init__(self):
        endpoint_url = os.getenv("S3_ENDPOINT_URL") or None  # None = AWS S3 real

        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            # Path-style é necessário para MinIO; AWS S3 aceita os dois
            config=boto3.session.Config(s3={"addressing_style": "path"}) if endpoint_url else None,
        )

    # ------------------------------------------------------------------
    # Gerenciamento de buckets
    # ------------------------------------------------------------------

    def ensure_bucket_exists(self, bucket_name: str) -> None:
        """
        Verifica se o bucket existe. Caso não exista, ele será criado.
        """
        try:
            self.client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("404", "NoSuchBucket"):
                self.client.create_bucket(Bucket=bucket_name)
            else:
                raise

    def list_buckets(self) -> list[str]:
        """
        Retorna uma lista com os nomes de todos os buckets disponíveis no storage.
        """
        response = self.client.list_buckets()
        return [b["Name"] for b in response.get("Buckets", [])]

    # ------------------------------------------------------------------
    # Listagem de objetos
    # ------------------------------------------------------------------

    def list_objects(self, bucket_name: str, prefix: str = "") -> list[str]:
        """
        Lista todos os objetos dentro de um bucket com um determinado prefixo.
        Ideal para descobrir quais arquivos já foram processados (idempotência).
        Lida automaticamente com paginação do S3.
        """
        try:
            self.client.head_bucket(Bucket=bucket_name)
        except ClientError:
            return []

        paginator = self.client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

        return [
            obj["Key"]
            for page in pages
            for obj in page.get("Contents", [])
        ]

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_buffer(self, bucket_name: str, object_name: str, buffer: io.BytesIO) -> None:
        """
        Faz o upload de um objeto armazenado em memória (BytesIO) para o storage.
        - bucket_name: Nome do bucket destino (ex: 'terceirizados')
        - object_name: Caminho completo dentro do bucket (ex: 'raw/terceirizados_2025_janeiro.parquet')
        - buffer: Buffer com os dados carregados na memória RAM.
        """
        buffer.seek(0)
        self.client.upload_fileobj(buffer, bucket_name, object_name)

    def upload_file(self, bucket_name: str, object_name: str, file_path: str) -> None:
        """
        Faz o upload de um arquivo físico em disco para o storage.
        Útil nas etapas de transformação (ex: subir 'bronze.duckdb' gerado localmente).
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo local não encontrado: {file_path}")

        self.client.upload_file(file_path, bucket_name, object_name)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_file(self, bucket_name: str, object_name: str, file_path: str) -> str:
        """
        Baixa um objeto do storage diretamente para o disco local.
        Retorna o caminho do arquivo baixado (file_path).
        """
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        self.client.download_file(bucket_name, object_name, file_path)
        return file_path

    def get_object(self, bucket_name: str, object_name: str) -> io.BytesIO:
        """
        Faz o download de um objeto do storage e retorna como BytesIO em memória.
        Ideal para baixar arquivos Parquet e passar direto pro DuckDB sem salvar em disco.
        """
        response = self.client.get_object(Bucket=bucket_name, Key=object_name)
        buffer = io.BytesIO(response["Body"].read())
        buffer.seek(0)
        return buffer
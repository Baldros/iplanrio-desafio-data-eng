import os
import io
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import polars as pl
from minio import Minio
from tqdm import tqdm

# Carrega variáveis de ambiente (.env)
load_dotenv()

# Configurações do MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
BUCKET_NAME = "terceirizados"

def get_minio_client() -> Minio:
    """Retorna o client do MinIO configurado."""
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False  # HTTP local (não encriptado com TLS)
    )

def ensure_bucket_exists(client: Minio, bucket_name: str):
    """Garante que o bucket exista antes de fazermos upload."""
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        print(f"Bucket '{bucket_name}' criado com sucesso.")
    else:
        print(f"Bucket '{bucket_name}' já existe.")

def fetch_csv_links(url: str) -> list[str]:
    """Extrai os links de arquivos CSV da página de dados abertos da CGU."""
    print(f"Buscando links em: {url}")
    response = requests.get(url)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Normalmente, em sites do Gov.br, os arquivos CSV estão linkados diretamente na página
    # ou em botões específicos com a classe de download.
    csv_links = []
    
    # Procura todas as tags <a> com href
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if ".csv" in href.lower():
            csv_links.append(href)
            
    return list(set(csv_links))

def process_and_upload(csv_url: str, minio_client: Minio):
    """Faz o download do CSV, converte para Parquet usando Polars e sobe para o MinIO."""
    print(f"Baixando dados de: {csv_url}")
    
    # Baixa o conteúdo da URL
    response = requests.get(csv_url, stream=True)
    response.raise_for_status()

    # O Polars consegue ler diretamente os bytes baixados.
    # No caso de arquivos do governo, muitas vezes a codificação é ISO-8859-1 e os separadores são ;
    print("Carregando CSV com Polars...")
    try:
        df = pl.read_csv(response.content, separator=";", encoding="utf8-lossy", ignore_errors=True)
    except Exception as e:
        print(f"Falha ao ler em utf8-lossy, tentando ISO-8859-1: {e}")
        df = pl.read_csv(response.content, separator=";", encoding="iso-8859-1", ignore_errors=True)
        
    print(f"Dados processados. Linhas: {df.height}, Colunas: {df.width}")

    # Cria nome de arquivo Parquet baseado na URL
    # Ex: http://[...]/202501_Terceirizados.csv -> 202501_terceirizados.parquet
    file_name = csv_url.split("/")[-1].lower().replace(".csv", "")
    parquet_filename = f"raw/{file_name}.parquet"

    # Converte o DataFrame para Parquet em memória (num buffer)
    buffer = io.BytesIO()
    df.write_parquet(buffer)
    buffer.seek(0)
    
    # Faz upload para o MinIO
    print(f"Iniciando upload para MinIO: s3://{BUCKET_NAME}/{parquet_filename}")
    minio_client.put_object(
        bucket_name=BUCKET_NAME,
        object_name=parquet_filename,
        data=buffer,
        length=buffer.getbuffer().nbytes,
        content_type="application/octet-stream"
    )
    print(f"Upload finalizado com sucesso: {parquet_filename}\n")

def main():
    url = os.getenv("DATA_RESOUCES")
    if not url:
        raise ValueError("A variável de ambiente DATA_RESOUCES não foi encontrada.")

    # 1. Configura Client do Minio e o Bucket
    minio_client = get_minio_client()
    ensure_bucket_exists(minio_client, BUCKET_NAME)

    # 2. Varredura dos links
    csv_links = fetch_csv_links(url)
    print(f"Encontrados {len(csv_links)} arquivos CSV potenciais no HTML.")

    # 3. Processamento - como PoC (Proof of Concept) vamos processar apenas 1 primeiro.
    # Depois, isso será alterado para verificação de quais meses já existem.
    if csv_links:
        # Pega a primeiro URL CSV e envia para o pipeline
        primeiro_link = csv_links[0]
        process_and_upload(primeiro_link, minio_client)
    else:
        print("Nenhum CSV encontrado na página.")

if __name__ == "__main__":
    main()

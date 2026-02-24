"""
Módulo responsável pelo organização e orquestração do 
workflow de ingestão de dados e ETL no padrão da 
arquitetura Medallion.
"""

# Modulos do projeto
from scraper import ScrapingClient
from OStorage import OBJStorageClient
from engine import ELTEngine

# Dependências auxiliares
import os 
import io
from tqdm import tqdm
from time import time
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()

def main():
    print("=== Iniciando Extração RAW ===")
    
    # 1. Instanciando classes e Configurações
    url = os.getenv("DATA_RESOUCES")
    bucket_name = "terceirizados"
    prefix = "raw/"
    
    # Configuração centralizada do S3 para o motor ELT
    s3_config = {
        "endpoint": os.getenv("S3_ENDPOINT_URL", "localhost:9000"),
        "access_key_id": os.getenv("AWS_ACCESS_KEY_ID", ""),
        "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        "region": os.getenv("AWS_REGION", "us-east-1")
    }

    scrape = ScrapingClient(url)
    minio = OBJStorageClient()
    engine = ELTEngine() # O motor ELT cuida de DuckDB e dbt
    
    # Garante que o bucket exista
    minio.ensure_bucket_exists(bucket_name)

    # 2. Descobrir o que já temos no MinIO (Idempotência)
    objetos_existentes = minio.list_objects(bucket_name, prefix=prefix)
    chaves_processadas = set()
    
    for obj in objetos_existentes:
        filename = obj.split("/")[-1]
        if filename.startswith("terceirizados_") and filename.endswith(".parquet"):
            key = filename.replace("terceirizados_", "").replace(".parquet", "")
            chaves_processadas.add(key)
            
    # 3. Mapear links disponíveis na origem
    links_dict = scrape.get_links()

    # 4. Cruzamento e Download
    baixados = 0
    for ano, meses in tqdm(links_dict.items(), desc="Processando dados."):
        for mes, link in meses.items():
            chave_do_arquivo = f"{ano}_{mes.lower()}"
            
            if chave_do_arquivo in chaves_processadas:
                continue
                
            try:
                df = scrape.download_data(link, ano, mes)
                
                buffer = io.BytesIO()
                df.write_parquet(buffer)
                
                object_name = f"{prefix}terceirizados_{chave_do_arquivo}.parquet"
                minio.upload_buffer(bucket_name, object_name, buffer)
                baixados += 1
                
            except Exception as e:
                print(f"[Flow] Erro ao processar {ano}-{mes}: {e}")
        
    # 5. Camada BRONZE (Apenas se houve novidades)
    if baixados > 0:
        print("\n=== Camada BRONZE ===")
        file_path = engine.create_bronze(s3_config, bucket_name=bucket_name, prefix=prefix)
        
        object_name_bronze = "bronze/terceirizados-bronze.duckdb"
        minio.upload_file(bucket_name, object_name_bronze, file_path)
        print("[Flow] Bronze atualizada no MinIO!")
        
    # 6. Camada SILVER
    print("\n=== Camada SILVER ===")
    
    tmp_path = os.path.join(os.getcwd(), "tmp")
    local_bronze = os.path.join(tmp_path, "terceirizados-bronze.duckdb")
    local_silver = os.path.join(tmp_path, "terceirizados-silver.duckdb")
    local_gold   = os.path.join(tmp_path, "terceirizados-gold.duckdb")

    object_name_bronze = "bronze/terceirizados-bronze.duckdb"
    object_name_silver = "silver/terceirizados-silver.duckdb"
    object_name_gold   = "gold/terceirizados-gold.duckdb"

    # 6.1 Garantir Bronze local
    if not os.path.exists(local_bronze):
        print(f"[Flow] Baixando Bronze para dbt...")
        minio.download_file(bucket_name, object_name_bronze, local_bronze)
    
    # 6.2 Executar Silver via Engine
    try:
        engine.run_dbt(target="silver")
        
        if os.path.exists(local_silver):
            minio.upload_file(bucket_name, object_name_silver, local_silver)
            print("[Flow] Silver atualizada no MinIO!")
            
    except Exception as e:
        print(f"[Flow] Erro Silver: {e}")

    # 7. Camada GOLD
    print("\n=== Camada GOLD ===")
    try:
        if not os.path.exists(local_silver):
             minio.download_file(bucket_name, object_name_silver, local_silver)

        engine.run_dbt(target="gold")

        if os.path.exists(local_gold):
            minio.upload_file(bucket_name, object_name_gold, local_gold)
            print("[Flow] Gold atualizada no MinIO!")

    except Exception as e:
        print(f"[Flow] Erro Gold: {e}")

    # 8. Limpeza Geral
    print("\n[Flow] Limpando arquivos temporários...")
    for f in [local_bronze, local_silver, local_gold]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception as e:
                print(f"[Flow] Alerta ao remover {f}: {e}")

    if baixados == 0:
        print("\n[Flow] Nenhuma novidade encontrada.")
    else:
        print(f"\n[Flow] Fluxo finalizado! {baixados} novos arquivos RAW adicionados.")

if __name__ == "__main__":
    start = time()
    main()
    end = time()
    print(f"\n[Flow] Tempo total: {end - start:.2f} segundos.")

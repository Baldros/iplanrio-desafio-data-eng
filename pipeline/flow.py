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
from dotenv import load_dotenv
from typing import Dict, Any

# Prefect v3
from prefect import flow, task, get_run_logger

# Carregar variáveis do .env
load_dotenv()

@task(name="Get Configuration", description="Carregar variáveis de ambiente e instanciar clientes.")
def get_config() -> Dict[str, Any]:
    logger = get_run_logger()
    logger.info("Carregando configurações do ambiente...")
    
    config = {
        "data_resource_url": os.getenv("DATA_RESOUCES"),
        "bucket_name": "terceirizados",
        "raw_prefix": "raw/",
        "s3_config": {
            "endpoint": os.getenv("S3_ENDPOINT_URL", "localhost:9000"),
            "access_key_id": os.getenv("AWS_ACCESS_KEY_ID", ""),
            "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
            "region": os.getenv("AWS_REGION", "us-east-1")
        },
        "tmp_paths": {
            "bronze": os.path.join(os.getcwd(), "tmp", "terceirizados-bronze.duckdb"),
            "silver": os.path.join(os.getcwd(), "tmp", "terceirizados-silver.duckdb"),
            "gold": os.path.join(os.getcwd(), "tmp", "terceirizados-gold.duckdb")
        }
    }
    return config

@task(name="Ingest Raw Data", description="Descobrir e baixar novos arquivos RAW para o MinIO.", retries=2)
def ingest_raw_data(config: Dict[str, Any]) -> int:
    logger = get_run_logger()
    scrape = ScrapingClient(config["data_resource_url"])
    minio = OBJStorageClient()
    
    bucket_name = config["bucket_name"]
    prefix = config["raw_prefix"]
    
    # Garante que o bucket exista
    minio.ensure_bucket_exists(bucket_name)

    logger.info(f"Verificando arquivos existentes em s3://{bucket_name}/{prefix}")
    objetos_existentes = minio.list_objects(bucket_name, prefix=prefix)
    chaves_processadas = {
        obj.split("/")[-1].replace("terceirizados_", "").replace(".parquet", "")
        for obj in objetos_existentes 
        if obj.endswith(".parquet")
    }
            
    links_dict = scrape.get_links()
    baixados = 0
    
    for ano, meses in links_dict.items():
        for mes, link in meses.items():
            chave_do_arquivo = f"{ano}_{mes.lower()}"
            
            if chave_do_arquivo in chaves_processadas:
                continue
                
            try:
                logger.info(f"Baixando e processando: {ano}-{mes}")
                df = scrape.download_data(link, ano, mes)
                
                buffer = io.BytesIO()
                df.write_parquet(buffer)
                
                object_name = f"{prefix}terceirizados_{chave_do_arquivo}.parquet"
                minio.upload_buffer(bucket_name, object_name, buffer)
                baixados += 1
                
            except Exception as e:
                logger.error(f"[Flow] Erro ao processar {ano}-{mes}: {e}")
                raise e
                
    return baixados

@task(name="Build Bronze Layer", description="Consolidar Parquets na camada Bronze e subir para S3.")
def build_bronze_layer(config: Dict[str, Any]):
    logger = get_run_logger()
    engine = ELTEngine()
    minio = OBJStorageClient()
    
    logger.info("Iniciando criação da camada BRONZE...")
    file_path = engine.create_bronze(
        config["s3_config"], 
        bucket_name=config["bucket_name"], 
        prefix=config["raw_prefix"]
    )
    
    object_name_bronze = "bronze/terceirizados-bronze.duckdb"
    minio.upload_file(config["bucket_name"], object_name_bronze, file_path)
    logger.info(f"Camada Bronze atualizada e enviada para s3://{config['bucket_name']}/{object_name_bronze}")

@task(name="Run DBT Transformation", description="Executar transformações dbt (Silver/Gold).")
def run_dbt_transformation(target: str, config: Dict[str, Any]):
    logger = get_run_logger()
    engine = ELTEngine()
    minio = OBJStorageClient()
    
    bucket_name = config["bucket_name"]
    local_bronze = config["tmp_paths"]["bronze"]
    local_target = config["tmp_paths"][target]
    
    object_name_bronze = "bronze/terceirizados-bronze.duckdb"
    object_name_target = f"{target}/terceirizados-{target}.duckdb"

    # dbt-duckdb gerencia os paths se configurado no profiles.yml
    # O flow original baixava manualmente a Bronze se necessário.
    
    if target == "silver" and not os.path.exists(local_bronze):
        logger.info("Baixando Bronze para execução do dbt Silver...")
        minio.download_file(bucket_name, object_name_bronze, local_bronze)
    
    if target == "gold" and not os.path.exists(config["tmp_paths"]["silver"]):
        logger.info("Baixando Silver para execução do dbt Gold...")
        minio.download_file(bucket_name, "silver/terceirizados-silver.duckdb", config["tmp_paths"]["silver"])

    logger.info(f"Executando dbt run para target: {target}")
    engine.run_dbt(target=target)
    
    if os.path.exists(local_target):
        minio.upload_file(bucket_name, object_name_target, local_target)
        logger.info(f"Camada {target.upper()} atualizada no MinIO!")

@task(name="Cleanup Local Storage", description="Limpar arquivos temporários .duckdb.")
def cleanup_local_storage(config: Dict[str, Any]):
    logger = get_run_logger()
    logger.info("Limpando arquivos temporários...")
    for path in config["tmp_paths"].values():
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Removido: {path}")
            except Exception as e:
                logger.warning(f"Erro ao remover {path}: {e}")

@flow(name="Medallion ELT Pipeline", log_prints=True)
def medallion_pipeline():
    logger = get_run_logger()
    logger.info("Iniciando o Medallion Pipeline Orchestration")
    
    # 1. Configuração
    config = get_config()
    
    # 2. Ingestão RAW
    baixados = ingest_raw_data(config)
    
    # 3. Camadas (Bronze -> Silver -> Gold)
    if baixados > 0:
        build_bronze_layer(config)
    else:
        logger.info("Nenhuma novidade RAW. Pulando atualização da camada Bronze.")

    run_dbt_transformation("silver", config)
    run_dbt_transformation("gold", config)
    
    # 4. Limpeza
    cleanup_local_storage(config)
    
    logger.info(f"Pipeline concluído. Novos arquivos RAW: {baixados}")

if __name__ == "__main__":
    medallion_pipeline()

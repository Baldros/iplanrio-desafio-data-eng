"""
Módulo responsável pelo organização e orquestração do 
workflow de ingestão de dados e ETL no padrão da 
arquitetura Medallion.
"""


# Modulos do projeto
from scraper import ScrapingClient
from OStorage import OBJStorageClient
from RStorage import DuckDBClient
from dbt_runner import DbtRunner

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
    
    # 1. Instanciando classes
    url = os.getenv("DATA_RESOUCES")
    bucket_name = "terceirizados"
    prefix = "raw/"
    
    scrape = ScrapingClient(url)
    minio = OBJStorageClient()
    duck_client = DuckDBClient()
    dbt = DbtRunner()
    
    # Garante que o bucket exista
    minio.ensure_bucket_exists(bucket_name)

    # 2. Descobrir o que já temos no MinIO (Idempotência)
    #print("\n[Flow] Verificando arquivos existentes no MinIO...")
    objetos_existentes = minio.list_objects(bucket_name, prefix=prefix)
    chaves_processadas = set()
    
    for obj in objetos_existentes:
        # Pega a parte final, ex: "raw/terceirizados_2025_janeiro.parquet" -> "2025_janeiro"
        filename = obj.split("/")[-1]
        if filename.startswith("terceirizados_") and filename.endswith(".parquet"):
            key = filename.replace("terceirizados_", "").replace(".parquet", "")
            chaves_processadas.add(key)
            
    #print(f"[Flow] Encontrados {len(chaves_processadas)} arquivos já processados.")

    # 3. Mapear links disponíveis na origem
    #print("\n[Flow] Mapeando novos links no site...")
    links_dict = scrape.get_links()

    # 4. Cruzamento e Download
    baixados = 0
    for ano, meses in tqdm(links_dict.items(),desc ="Processando dados."):
        for mes, link in meses.items():
            chave_do_arquivo = f"{ano}_{mes.lower()}"
            
            if chave_do_arquivo in chaves_processadas:
                # O arquivo já existe no Minio, não precisamos baixar.
                continue
                
            #print(f"\n[Flow] Novo dado detectado! Baixando {ano}-{mes}...")
            
            try:
                # Faz scraping e converte o csv/zip sujo em Polars Dataframe
                df = scrape.download_data(link, ano, mes)
                
                # Converte o Dataframe em um arquivo Parquet seguro dentro da memória RAM
                buffer = io.BytesIO()
                df.write_parquet(buffer)
                
                # Envia o Parquet da memória RAM pro Minio
                object_name = f"{prefix}terceirizados_{chave_do_arquivo}.parquet"
                minio.upload_buffer(bucket_name, object_name, buffer)
                
                baixados += 1
                
            except Exception as e:
                print(f"[Flow] Erro ao processar {ano}-{mes}: {e}")
        
    # 5. Criar a Camada Bronze (Apenas se houve novidades)
    if baixados > 0:
        print("\n=== Iniciando Camada BRONZE ===")
        
        # 5.1 O DuckDBClient conecta ao s3, lê todos os parquets raw, e gera o arquivo físico local consolidado
        file_path = duck_client.create_bronze(bucket_name=bucket_name, prefix=prefix)
        
        # 5.2 O MinIO Client pega esse arquivo e posta na pasta da bronze
        object_name_bronze = "bronze/terceirizados-bronze.duckdb"
        minio.upload_file(bucket_name, object_name_bronze, file_path)
        print("\n[Flow] Camada Bronze atualizada com sucesso no MinIO!")
        
    # 6. Criar a Camada Silver
    print("\n=== Iniciando Camada SILVER ===")
    
    tmp_path = os.path.join(os.getcwd(), "tmp")
    os.makedirs(tmp_path, exist_ok=True)
    
    local_bronze = os.path.join(tmp_path, "terceirizados-bronze.duckdb")
    local_silver = os.path.join(tmp_path, "terceirizados-silver.duckdb")
    local_gold   = os.path.join(tmp_path, "terceirizados-gold.duckdb")

    object_name_bronze = "bronze/terceirizados-bronze.duckdb"
    object_name_silver = "silver/terceirizados-silver.duckdb"
    object_name_gold   = "gold/terceirizados-gold.duckdb"

    # 6.1 Garantir que temos o bronze localmente para o dbt
    if not os.path.exists(local_bronze):
        print(f"[Flow] Baixando a base Bronze do MinIO para processamento dbt...")
        minio.download_file(bucket_name, object_name_bronze, local_bronze)
    
    # 6.2 Executar o dbt via DbtRunner (Silver)
    try:
        dbt.run_silver()
        
        if os.path.exists(local_silver):
            print(f"[Flow] Enviando Camada Silver para o MinIO...")
            minio.upload_file(bucket_name, object_name_silver, local_silver)
            print("[Flow] Camada Silver atualizada com sucesso no MinIO!")
            
    except Exception as e:
        print(f"[Flow] Erro durante a criação da camada Silver: {e}")

    # 7. Criar a Camada Gold
    print("\n=== Iniciando Camada GOLD ===")
    try:
        # 7.1 Garantir que temos o silver localmente (caso tenha falhado o passo anterior ou queiramos rodar gold isolado)
        if not os.path.exists(local_silver):
             print(f"[Flow] Baixando a base Silver do MinIO para processamento dbt Gold...")
             minio.download_file(bucket_name, object_name_silver, local_silver)

        # 7.2 Executar o dbt via DbtRunner (Gold)
        dbt.run_gold()

        if os.path.exists(local_gold):
            print(f"[Flow] Enviando Camada Gold para o MinIO...")
            minio.upload_file(bucket_name, object_name_gold, local_gold)
            print("[Flow] Camada Gold atualizada com sucesso no MinIO!")

    except Exception as e:
        print(f"[Flow] Erro durante a criação da camada Gold: {e}")

    # 8. Limpeza Geral
    print("\n[Flow] Finalizando e limpando arquivos temporários...")
    for f in [local_bronze, local_silver, local_gold]:
        if os.path.exists(f):
            os.remove(f)

    if baixados == 0:
        print("\n[Flow] Banco de dados RAW 100% atualizado. Nenhuma novidade encontrada.")
    else:
        print(f"\n[Flow] Fluxo finalizado! {baixados} novos arquivos RAW adicionados.")

if __name__ == "__main__":
    start = time()
    main()
    end = time()
    print(f"\n[Flow] Tempo total de execução: {end - start} segundos.")

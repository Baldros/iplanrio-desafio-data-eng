"""
Módulo responsável pelo organização e orquestração do 
workflow de ingestão de dados e ETL no padrão da 
arquitetura Medallion.
"""


# Modulos do projeto
from scraper import ScrapingClient
from OStorage import MinioClient
from RStorage import DuckDBClient

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
    minio = MinioClient()
    duck_client = DuckDBClient()
    
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
        os.remove(file_path) # Limpeza local
        print("\n[Flow] Camada Bronze atualizada com sucesso no MinIO!")
        
    if baixados == 0:
        print("\n[Flow] Banco de dados RAW 100% atualizado. Nenhuma novidade encontrada.")
    else:
        print(f"\n[Flow] Fluxo finalizado! {baixados} novos arquivos RAW adicionados.")

if __name__ == "__main__":
    start = time()
    main()
    end = time()
    print(f"\n[Flow] Tempo total de execução: {end - start} segundos.")

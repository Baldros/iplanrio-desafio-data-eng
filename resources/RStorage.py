import os
import duckdb
import pyarrow.parquet as pq


class DuckDBClient:
    """
    Responsável por criar e popular o banco bronze a partir
    dos Parquets armazenados no MinIO.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def criar_bronze(self, minio_client, bucket: str, prefix: str = "raw/") -> None:
        """
        Lê todos os Parquets do MinIO e consolida num único arquivo bronze.duckdb.
        Recria o banco do zero a cada execução (idempotência).
        """
        # Apaga o banco anterior para garantir idempotência
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        conn = duckdb.connect(self.db_path)

        conn.execute("""
            CREATE TABLE terceirizados (
                id_terc                   VARCHAR,
                sg_orgao_sup_tabela_ug    VARCHAR,
                cd_ug_gestora             VARCHAR,
                nm_ug_tabela_ug           VARCHAR,
                sg_ug_gestora             VARCHAR,
                nr_contrato               VARCHAR,
                nr_cnpj                   VARCHAR,
                nm_razao_social           VARCHAR,
                nr_cpf                    VARCHAR,
                nm_terceirizado           VARCHAR,
                nm_categoria_profissional VARCHAR,
                nm_escolaridade           VARCHAR,
                nr_jornada                INTEGER,
                nm_unidade_prestacao      VARCHAR,
                vl_mensal_salario         DOUBLE,
                vl_mensal_custo           DOUBLE,
                num_mes_carga             INTEGER,
                mes_carga                 VARCHAR,
                ano_carga                 INTEGER,
                sg_orgao                  VARCHAR,
                nm_orgao                  VARCHAR,
                cd_orgao_siafi            VARCHAR,
                cd_orgao_siape            VARCHAR
            )
        """)

        parquets = minio_client.list_objects(bucket, prefix=prefix)

        for object_name in parquets:
            print(f"[DuckDB] Processando {object_name}...")

            buffer = minio_client.download_object(bucket, object_name)
            arrow_table = pq.read_table(buffer)

            conn.register("temp_parquet", arrow_table)
            conn.execute("INSERT INTO terceirizados SELECT * FROM temp_parquet")
            conn.unregister("temp_parquet")

        conn.close()
        print(f"[DuckDB] Bronze gerado em {self.db_path}")
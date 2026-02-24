import os
import subprocess
import sys
import duckdb

class ELTEngine:
    """
    Engine central para orquestração de processos ELT.
    Consolida o carregamento da camada Bronze (DuckDB + S3) e 
    transfomações dbt (Silver/Gold).
    """

    def __init__(self, dbt_project_dir: str = None):
        """
        Inicializa o motor ELT.
        :param dbt_project_dir: Caminho absoluto para o diretório do dbt.
        """
        self.dbt_project_dir = dbt_project_dir or self._infer_dbt_project_dir()
        self.dbt_executable = self._find_dbt_executable()
        
        # Paths padrão para o DuckDB (podem ser customizados se necessário)
        self.tmp_dir = os.path.join(os.getcwd(), "tmp")
        os.makedirs(self.tmp_dir, exist_ok=True)
        self.bronze_path = os.path.join(self.tmp_dir, "terceirizados-bronze.duckdb")

    def _infer_dbt_project_dir(self) -> str:
        """Infere o diretório dbt a partir do contexto atual."""
        current_dir = os.getcwd()
        if os.path.basename(current_dir) == "pipeline":
            return os.path.join(os.path.dirname(current_dir), "dbt")
        return os.path.join(current_dir, "dbt")

    def _find_dbt_executable(self) -> str:
        """Tenta encontrar o executável do dbt no ambiente atual."""
        python_bin_dir = os.path.dirname(sys.executable)
        dbt_exe = os.path.join(python_bin_dir, "dbt.exe")
        if os.path.exists(dbt_exe):
            return dbt_exe
        return "dbt"

    def create_bronze(self, s3_config: dict, bucket_name: str, prefix: str = "raw/", table_name: str = "terceirizados") -> str:
        """
        Cria a camada Bronze consolidando Parquets do S3 no DuckDB.
        :param s3_config: Dicionário com keys: endpoint, access_key_id, secret_access_key, region.
        """
        print(f"[Engine] Criando Camada Bronze no banco {self.bronze_path}...")
            
        conn = duckdb.connect(self.bronze_path)
        
        try:
            conn.execute("INSTALL httpfs; LOAD httpfs;")
            
            # Configurações S3 via injeção de parâmetros
            conn.execute(f"SET s3_endpoint='{s3_config['endpoint'].replace('http://', '').replace('https://', '')}';")
            conn.execute(f"SET s3_access_key_id='{s3_config['access_key_id']}';")
            conn.execute(f"SET s3_secret_access_key='{s3_config['secret_access_key']}';")
            conn.execute(f"SET s3_region='{s3_config['region']}';")
            conn.execute("SET s3_use_ssl=false; SET s3_url_style='path';")
            
            query = f"""CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet('s3://{bucket_name}/{prefix}*.parquet', union_by_name=true)"""
            conn.execute(query)
            print(f"[Engine] Camada Bronze criada com sucesso.")
            
        finally:
            conn.close()

        return self.bronze_path

    def run_dbt(self, target: str, select: str = None) -> str:
        """
        Executa comandos dbt.
        :param target: Alvo do dbt (silver ou gold).
        :param select: Seletor (silver, gold, etc). Se None, assume o mesmo que o target.
        """
        selector = select or target
        print(f"[Engine] dbt run --target {target} --select {selector}...")
        
        command = [self.dbt_executable, "run", "--target", target, "--select", selector]

        try:
            result = subprocess.run(
                command,
                cwd=self.dbt_project_dir,
                check=True,
                capture_output=True,
                text=True
            )
            print(f"[Engine] dbt {target} concluído.")
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            print(f"[Engine] Falha dbt:\n{e.stderr or e.stdout}")
            raise e

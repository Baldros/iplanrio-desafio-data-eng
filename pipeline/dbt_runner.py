import os
import subprocess
import sys

class DbtRunner:
    """
    Classe responsável por orquestrar a execução do dbt (Data Build Tool).
    Essa classe é agnóstica ao orquestrador (ex: Prefect) e foca apenas
    na execução dos comandos dbt via subprocess.
    """

    def __init__(self, dbt_project_dir: str = None):
        """
        Inicializa o DbtRunner.
        :param dbt_project_dir: Caminho absoluto para o diretório do projeto dbt.
                                Se não for informado, assume que o dbt/ está na raiz do projeto.
        """
        # Identificar o executável do dbt
        self.dbt_executable = self._find_dbt_executable()
        
        if dbt_project_dir:
            self.dbt_project_dir = dbt_project_dir
        else:
            # Assume que estamos rodando a partir da raiz do projeto ou da pasta pipeline/
            # e que a pasta dbt/ está na raiz.
            current_dir = os.getcwd()
            if os.path.basename(current_dir) == "pipeline":
                self.dbt_project_dir = os.path.join(os.path.dirname(current_dir), "dbt")
            else:
                self.dbt_project_dir = os.path.join(current_dir, "dbt")

    def _find_dbt_executable(self) -> str:
        """Tenta encontrar o executável do dbt no ambiente atual."""
        # 1. Tentar encontrar no mesmo diretório do python (útil para venvs)
        python_bin_dir = os.path.dirname(sys.executable)
        dbt_exe = os.path.join(python_bin_dir, "dbt.exe")
        if os.path.exists(dbt_exe):
            return dbt_exe
        
        # 2. Tentar dbt (assumindo que está no PATH)
        return "dbt"

    def run(self, select: str = None, target: str = "silver") -> str:
        """
        Executa o comando 'dbt run'.
        :param select: Seletor de modelos (ex: 'silver', 'tag:gold').
        :param target: Alvo do dbt (ex: 'silver', 'gold').
        :return: A saída do stdout do dbt.
        """
        print(f"[dbt] Iniciando processo de execução dbt (target: {target}) usando {self.dbt_executable}...")
        
        command = [self.dbt_executable, "run", "--target", target]
        if select:
            command.extend(["--select", select])

        try:
            result = subprocess.run(
                command,
                cwd=self.dbt_project_dir,
                check=True,
                capture_output=True,
                text=True
            )
            print(f"[dbt] Execução concluída com sucesso para o target: {target}")
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            print(f"[dbt] Falha durante a execução do dbt:\n{e.stderr or e.stdout}")
            raise e

    def run_silver(self) -> str:
        """Helper para rodar a camada Silver."""
        return self.run(select="silver", target="silver")

    def run_gold(self) -> str:
        """Helper para rodar a camada Gold."""
        return self.run(select="gold", target="gold")

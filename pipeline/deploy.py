import os
import sys

# Adiciona o diretório atual ao path para garantir que o import do flow funcione
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importa o flow sem executá-lo
from flow import medallion_pipeline

if __name__ == "__main__":
    # serve() roda o flow como um servidor local (long-running process)
    # que escuta e executa runs agendados — ideal quando o código já
    # está presente no container (sem necessidade de image/storage).
    medallion_pipeline.serve(
        name="medallion-elt-deployment",
        # Roda às 00:00 do dia 1 de Janeiro, Maio e Setembro (Carga quadrimestral)
        cron="0 0 1 1,5,9 *",
        description="Pipeline ELT Medallion para Terceirizados - IPLANRIO (Orquestração a cada 4 meses)",
    )

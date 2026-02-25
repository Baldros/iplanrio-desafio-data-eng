from prefect import flow
from prefect.schedules import CronSchedule
import os
import sys

# Adiciona o diretório atual ao path para garantir que o import do flow funcione
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importa o flow sem executá-lo
from flow import medallion_pipeline

if __name__ == "__main__":
    # Registra o deployment no Prefect Server
    medallion_pipeline.deploy(
        name="medallion-elt-deployment",
        work_pool_name="default-agent-pool",
        # Roda às 00:00 do dia 1 de Janeiro, Maio e Setembro (Carga quadrimestral)
        schedule=CronSchedule("0 0 1 1,5,9 *"),
        description="Pipeline ELT Medallion para Terceirizados - IPLANRIO (Orquestração a cada 4 meses)",
        build=False # Como o código já está montado no volume/container
    )
    print("Deployment 'medallion-elt-deployment' registrado com sucesso!")

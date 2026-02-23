# Arquitetura de Processamento — Desafio Data Engineer IPLANRIO

## Visão Geral

O sistema é composto por um pipeline de dados orquestrado pelo Prefect, que percorre todas as etapas desde a aquisição dos dados brutos até a exposição via API REST. O Objective Storage (MinIO em dev, S3 em prod) é o hub central de armazenamento — tanto dos dados brutos quanto dos bancos processados de cada camada.

---

## Fluxo Completo

```
Scraping (gov.br)
      ↓
  Parquet (raw)  →  MinIO/S3 (raw/)
                          ↓
                    DuckDB lê e processa
                          ↓
               bronze.duckdb  →  MinIO/S3 (bronze/)
                          ↓
                    DBT transforma
                          ↓
               silver.duckdb  →  MinIO/S3 (silver/)
                          ↓
                    DBT transforma
                          ↓
                gold.duckdb   →  MinIO/S3 (gold/)
                          ↓
                    API baixa gold.duckdb
                          ↓
                       API REST
```

---

## Organização do Bucket

```
terceirizados/
├── raw/
│   ├── terceirizados_2024-01.parquet
│   ├── terceirizados_2024-05.parquet
│   └── ...
├── bronze/
│   └── terceirizados-bronze.duckdb
├── silver/
│   └── terceirizados-silver.duckdb
└── gold/
    └── terceirizados-gold.duckdb
```

---

## Etapas Detalhadas

### 1. Aquisição dos Dados (Scraping)

O scraping acessa o portal de Dados Abertos da CGU e coleta os arquivos mensais de terceirizados. A classe responsável pelo scraping é Prefect-agnóstica — ela apenas expõe métodos que o flow principal consome.

O dado coletado é estruturado numa classe própria e serializado no formato Parquet, um arquivo por mês disponível.

**Detecção de novidades (idempotência):** antes de baixar qualquer arquivo, o pipeline compara os meses disponíveis no site com os arquivos já presentes no MinIO (`raw/`). Apenas os meses novos são processados. Se não houver novidade, o flow encerra sem reprocessar nada.

```python
disponiveis = scraping_client.listar_meses()    # o que o site oferece
ja_processados = minio_client.listar_raw()       # o que já está no bucket
novos = set(disponiveis) - set(ja_processados)  # só o delta
```

---

### 2. Raw Storage — MinIO / S3

O MinIO é um servidor de object storage que roda em container Docker e expõe a mesma API do S3 da AWS. Em desenvolvimento, os Parquets ficam no MinIO (dados em disco local). Em produção, ficam no S3 (dados em nuvem).

O código é idêntico nos dois ambientes — apenas as variáveis de ambiente mudam (`endpoint`, `access_key`, `secret_key`).

**Importante:** o MinIO/S3 não armazena apenas os dados brutos. Ele é usado em todas as camadas — os arquivos `.duckdb` gerados em cada etapa também são enviados para o bucket, cada um na sua respectiva pasta.

---

### 3. Camada Bronze — DuckDB

O DuckDB lê os Parquets diretamente do MinIO via `httpfs` e consolida os dados num único arquivo `bronze.duckdb`. Esse banco é salvo localmente (volume Docker) durante o processamento e depois enviado para o MinIO (`bronze/`).

O `bronze.duckdb` não é apenas uma tabela — é um banco com schema definido, tipos corretos e dados consolidados de todos os meses disponíveis.

**Sobre o predicate pushdown:** nas etapas de transformação (raw → bronze → silver → gold), todos os dados precisam ser lidos integralmente. O predicate pushdown do DuckDB só traz benefício real na camada de consumo (API), onde as queries são seletivas.

---

### 4. Camadas Silver e Gold — DBT + DuckDB

O DBT conecta no DuckDB e executa modelos SQL que transformam os dados de uma camada para a próxima. Cada camada é um arquivo `.duckdb` separado.

**Silver:** limpeza, padronização de colunas conforme o manual de estilo da IPLANRIO, remoção de duplicatas, validações de qualidade.

**Gold:** modelo final orientado ao consumo pela API, com os campos e estrutura definidos pelo desafio.

O DBT é chamado pelo Prefect via subprocess — ele não é executado diretamente em Python, mas sim como ferramenta de linha de comando dentro do flow:

```python
@task
def run_dbt(layer: str):
    subprocess.run(
        ["dbt", "run", "--select", f"tag:{layer}"],
        cwd="/dbt",
        check=True
    )
```

Após cada execução do DBT, o arquivo `.duckdb` gerado é enviado para o MinIO na pasta correspondente.

---

### 5. Orquestração — Prefect

O Prefect orquestra todas as etapas num único flow sequencial, agendado para rodar a cada ~4 meses. Cada etapa é uma `@task`, e o flow principal as conecta em ordem.

**Estrutura do código:**

```
pipeline/
├── scraping.py      # ScrapingClient — coleta e estrutura os dados
├── storage.py       # MinioClient — upload, download, listagem
├── database.py      # DuckDBClient — leitura de Parquets, geração do bronze
├── dbt_runner.py    # DBTRunner — execução do DBT via subprocess
└── flow.py          # Flow principal — orquestra todas as tasks com Prefect
```

Os módulos são Prefect-agnósticos. Apenas o `flow.py` conhece o Prefect — isso facilita testar cada módulo isoladamente e mantém o código limpo.

**Flow principal:**

```python
@flow
def pipeline_terceirizados():
    novos_meses = detectar_novidades()      # Task 1: compara site vs MinIO
    if not novos_meses:
        return                              # nada novo, encerra
    salvar_raw(novos_meses)                 # Task 2: Parquet → MinIO (raw/)
    gerar_bronze()                          # Task 3: Parquets → bronze.duckdb → MinIO
    run_dbt("silver")                       # Task 4: bronze → silver.duckdb → MinIO
    run_dbt("gold")                         # Task 5: silver → gold.duckdb → MinIO
```

---

### 6. API REST — Consumo da Camada Gold

A API baixa o `gold.duckdb` do MinIO na inicialização e serve as requisições lendo desse arquivo local. Um mecanismo de cache em memória reduz o tempo de resposta para requisições frequentes.

Nesta etapa, o predicate pushdown do DuckDB é aproveitado — as queries da API são seletivas (busca por ID, paginação), então o DuckDB busca apenas os dados necessários.

Os endpoints expostos são:

- `GET /terceirizados` — lista paginada com ID, sigla do órgão, CNPJ e CPF
- `GET /terceirizados/{id}` — todos os dados do gold para o terceirizado especificado

---

## Decisões Arquiteturais Relevantes

| Decisão | Escolha | Justificativa |
|---|---|---|
| Object storage local | MinIO | Drop-in replacement do S3, sem custo, mesmo código |
| Formato de armazenamento raw | Parquet | Colunar, comprimido, suportado nativamente pelo DuckDB |
| Banco por camada | `.duckdb` separado por camada | Requisito explícito do desafio |
| Processamento local vs streaming | Local (volume Docker) | Nas etapas de transformação todos os dados são necessários; streaming não traz vantagem |
| Acoplamento do Prefect | Só no `flow.py` | Módulos testáveis independentemente, sem dependência do Prefect |
| Detecção de novidades | Comparação MinIO vs site | Simples, sem estado externo, idempotente por natureza |
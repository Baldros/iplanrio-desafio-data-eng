# Arquitetura de Processamento — Desafio Data Engineer IPLANRIO

## Visão Geral

O sistema é composto por um pipeline de dados modular escrito em Python, que percorre todas as etapas desde a aquisição dos dados brutos até a exposição via API REST. O Objective Storage (MinIO em dev, S3 em prod) é o hub central de armazenamento — tanto dos dados brutos quanto dos arquivos `.duckdb` processados de cada camada.

---

## Fluxo Completo

```
Scraping (gov.br)
      ↓
  Parquet (raw)  →  MinIO/S3 (raw/)
                          ↓
                ELTEngine (DuckDB) processa
                          ↓
               bronze.duckdb  →  MinIO/S3 (bronze/)
                          ↓
                ELTEngine (dbt silver)
                          ↓
               silver.duckdb  →  MinIO/S3 (silver/)
                          ↓
                ELTEngine (dbt gold)
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
│   ├── terceirizados_2024_janeiro.parquet
│   ├── terceirizados_2024_fevereiro.parquet
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

O scraping (em `scraper.py`) acessa o portal de Dados Abertos da CGU e coleta os arquivos mensais de terceirizados. O dado coletado é convertido em Polars DataFrame e serializado no formato Parquet.

**Detecção de novidades (idempotência):** antes de baixar qualquer arquivo, o pipeline compara os meses disponíveis no site com os arquivos já presentes no MinIO (`raw/`). Apenas os meses novos são processados. Se não houver novidade (e a base bronze já existir), o download é ignorado.

---

### 2. Objective Storage — MinIO / S3

O `OBJStorageClient` (em `OStorage.py`) abstrai a comunicação com o S3. Em desenvolvimento, usamos MinIO via Docker. Em produção, os mesmos métodos funcionam com o Amazon S3.
O armazenamento é o ponto de sincronia entre os processos: os arquivos `.duckdb` gerados localmente em cada etapa são enviados para o bucket para persistência e compartilhamento.

---

### 3. Camada Bronze — DuckDB

O `ELTEngine` (`engine.py`) utiliza o DuckDB para ler os Parquets diretamente do MinIO via extensão `httpfs` e consolidá-los localmente em `terceirizados-bronze.duckdb`. As credenciais de acesso são injetadas pelo orquestrador (`flow.py`), mantendo o motor de processamento desacoplado das configurações de ambiente.

---

### 4. Camadas Silver e Gold — dbt + DuckDB

O `ELTEngine` orquestra a execução do dbt via subprocess. Cada camada corresponde a um comando dbt específico:

- **Silver:** Limpeza, padronização de colunas e validações de qualidade dbt (tests).
- **Gold:** Modelo final consolidado, com índices para otimização de consultas da API.

O motor utiliza o binário do dbt presente no ambiente virtual (`IWVenv`) e direciona o comando para o projeto dbt local.

---

### 5. Orquestração — Workflow Python

O `flow.py` orquestra todas as etapas em um fluxo sequencial. Ele é o responsável por centralizar as variáveis de ambiente, gerenciar os diretórios temporários e garantir que um passo só ocorra se o anterior for bem-sucedido.

**Estrutura do código (`pipeline/`):**

- `scraper.py`: Coleta e converte dados brutos em Parquet.
- `OStorage.py`: Interface para leitura/escrita no MinIO/S3.
- `engine.py`: Motor ELT que coordena DuckDB (Bronze) e dbt (Silver/Gold).
- `flow.py`: Orquestrador principal que integra todos os componentes.

---

### 6. API REST — Consumo da Camada Gold

A API consome o arquivo `terceirizados-gold.duckdb`. Ela baixa a versão mais recente do Objective Storage caso não exista localmente, garantindo que o serviço sempre sirva dados atualizados.

---

## Decisões Arquiteturais Relevantes

| Decisão | Escolha | Justificativa |
|---|---|---|
| Tecnologia de Processamento | DuckDB + dbt | Alta performance local para transformações relacionais e gestão de linhagem. |
| Banco por camada | `.duckdb` separado | Isolamento físico das camadas medonhas e facilidade de backup/upload individual. |
| Injeção de Dependência | Credentials via `flow.py` | Impede que módulos de lógica (`engine.py`) fiquem "poluídos" com variáveis de ambiente do SO. |
| Modularização ELT | `ELTEngine` consolidado | Facilita a manutenção ao centralizar o uso de subprocessos e conexões de banco. |
| Camada RAW | Parquet no S3 | Formato colunar eficiente para leitura direta via DuckDB (predicate pushdown). |

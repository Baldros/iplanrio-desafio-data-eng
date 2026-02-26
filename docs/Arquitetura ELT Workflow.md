# Arquitetura de Processamento — Desafio Data Engineer IPLANRIO

## Visão Geral

Pipeline ELT modular escrito em Python, orquestrado pelo **Prefect v3**, que percorre todas as etapas desde a aquisição dos dados brutos até a disponibilização via API REST. O Object Storage (MinIO em dev, AWS S3 em prod) é o hub central de armazenamento.

---

## Fluxo Completo

```
Portal CGU (gov.br)
       ↓  scraper.py (Polars)
   Parquet (raw/)  ──→  MinIO/S3     ← Idempotente: só baixa meses novos
       ↓  engine.py (DuckDB + httpfs)
   bronze.duckdb   ──→  MinIO/S3     ← Consolida todos os Parquets
       ↓  dbt run --target silver
   silver.duckdb   ──→  MinIO/S3     ← Incremental: só processa novos meses
       ↓  dbt run --target gold
    gold.duckdb    ──→  MinIO/S3     ← Incremental: modelo final com índices
       ↓  DuckDB ATTACH via S3
     API REST (FastAPI)              ← Cache TTL + paginação + filtros
```

---

## Organização do Bucket

```
terceirizados/
├── raw/
│   ├── terceirizados_2024_janeiro.parquet
│   ├── terceirizados_2024_maio.parquet
│   ├── terceirizados_2024_setembro.parquet
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

O `scraper.py` acessa o portal de Dados Abertos da CGU e coleta os arquivos quadrimestrais (Janeiro, Maio, Setembro) de terceirizados. O dado coletado é convertido em **Polars DataFrame** e serializado no formato **Parquet**.

**Idempotência:** antes de baixar, o pipeline compara os meses disponíveis no site com os arquivos já presentes no MinIO (`raw/`). Apenas os meses novos são processados — se não houver novidade, o pipeline encerra sem reprocessar.

---

### 2. Object Storage — MinIO / S3

O `OStorage.py` abstrai a comunicação com o S3 via **boto3**. Em desenvolvimento, utiliza MinIO via Docker. Em produção, os mesmos métodos funcionam com Amazon S3.

O armazenamento é o ponto de sincronia: os arquivos `.duckdb` gerados localmente são enviados ao bucket para persistência e acesso pela API.

---

### 3. Camada Bronze — DuckDB

O `ELTEngine` (`engine.py`) utiliza o DuckDB para ler os Parquets diretamente do MinIO via extensão `httpfs` e consolidá-los em `terceirizados-bronze.duckdb`. Utiliza `union_by_name=true` para lidar com eventuais variações de schema entre diferentes períodos.

As credenciais são injetadas pelo orquestrador (`flow.py`), mantendo o motor de processamento desacoplado das configurações de ambiente.

---

### 4. Camadas Silver e Gold — dbt + DuckDB

O `ELTEngine` orquestra a execução do dbt via subprocess. Ambas as camadas utilizam **materialização incremental**:

#### Silver (`terceirizados_silver.sql`)
- Limpeza e padronização de colunas conforme o [guia de estilo IPLANRIO](https://docs.dados.rio/data-lake/guia-de-estilo/convencoes-colunas)
- Cast de tipos (INTEGER, DOUBLE, DATE)
- Tratamento de formatos numéricos (`REPLACE(vl_mensal_salario, ',', '.')`)
- **Chave de incrementalidade**: `id_terceirizado` + `mes_referencia_data`
- **Filtro incremental**: processa apenas registros com `mes_referencia_data` maior que o máximo existente

#### Gold (`terceirizados_gold.sql`)
- Modelo final com todas as 23 colunas da Silver
- Índices criados via `post_hook`: `id_terceirizado` e `cpf`
- Mesmo critério de incrementalidade da Silver

#### Testes de Qualidade (`schema.yml`)
- `not_null` em colunas-chave (id, cpf, cnpj, mes_referencia)
- `accepted_values` para meses de carga (1, 5, 9)
- Descrição completa de todas as colunas em ambos os modelos

---

### 5. Orquestração — Prefect v3

O `flow.py` orquestra todas as etapas como **tasks Prefect** em um fluxo sequencial:

1. **Get Configuration** — Carrega variáveis de ambiente
2. **Ingest Raw Data** — Scraping + upload para S3 (idempotente)
3. **Build Bronze Layer** — Consolida Parquets em DuckDB
4. **dbt Silver** — Transformação incremental
5. **dbt Gold** — Modelo final incremental
6. **Upload layers** — Envia .duckdb gerados para S3
7. **Cleanup** — Remove arquivos temporários locais

O `deploy.py` registra o pipeline como um **deployment Prefect** com schedule quadrimestral (cron).

**Estrutura do código (`pipeline/`):**

| Arquivo | Responsabilidade |
|---|---|
| `scraper.py` | Coleta e converte dados brutos em Parquet |
| `OStorage.py` | Interface para leitura/escrita no MinIO/S3 |
| `engine.py` | Motor ELT: DuckDB (Bronze) + dbt (Silver/Gold) |
| `flow.py` | Orquestrador principal — integra todos os componentes |
| `deploy.py` | Registro do deployment Prefect com schedule |

---

### 6. API REST — Consumo da Camada Gold

A API conecta-se diretamente ao `gold.duckdb` no S3 via `ATTACH` (suportado pelo DuckDB + httpfs). Isso garante que sempre consuma a versão mais recente sem necessidade de download local.

> Para detalhes sobre endpoints, filtros e cache, consulte [Arquitetura da API REST](API%20Architecture.md).

---

## Decisões Arquiteturais

| Decisão | Escolha | Justificativa |
|---|---|---|
| Motor de processamento | DuckDB + dbt | Alta performance local para transformações analíticas e gestão de linhagem |
| Banco por camada | `.duckdb` separado | Isolamento físico das camadas e facilidade de backup/upload individual |
| Materialização dbt | Incremental | Evita reprocessar histórico a cada execução — essencial para o requisito de incrementalidade |
| Injeção de credenciais | Via `flow.py` | Mantém módulos de lógica (`engine.py`) desacoplados das variáveis de ambiente |
| Formato RAW | Parquet no S3 | Formato colunar eficiente para leitura direta via DuckDB (predicate pushdown) |
| Scraping incremental | Comparação com S3 | Idempotência: só baixa períodos não existentes no bucket |
| Conexão API → Gold | `ATTACH` via S3 | Conforme permitido pelo desafio + cache TTL para performance |

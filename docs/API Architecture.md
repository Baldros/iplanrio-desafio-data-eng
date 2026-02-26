# Arquitetura da API REST — Desafio IPLANRIO

## 1. Visão Geral

API REST construída com **FastAPI** para exposição dos dados da camada Ouro do pipeline Medallion. Oferece listagem paginada, busca por ID, filtros dinâmicos e endpoints analíticos, com cache em memória para otimização de performance.

## 2. Pilares de Design

### 2.1 Agnosticismo de Ambiente

A API se conecta ao banco Gold hospedado em S3 (ou MinIO) usando o `ATTACH` do DuckDB via extensão `httpfs`. As credenciais são gerenciadas via `CREATE SECRET`, permitindo troca transparente entre MinIO local e AWS S3.

```
API (FastAPI)
   ↓
DuckDB (in-memory) ──ATTACH──→ gold.duckdb (S3/MinIO)
   ↓
Endpoints REST
```

- **`config.py`** — Centraliza variáveis de ambiente via Pydantic `BaseSettings`
- **`database.py`** — Singleton `DatabaseManager` com `CREATE SECRET` para S3

### 2.2 Performance

- **TTLCache** — Cache em memória com expiração temporal (configurável via `CACHE_EXPIRE_SECONDS`), evitando re-consultas ao S3 para os mesmos parâmetros
- **Paginação obrigatória** — `page_size` máximo de 100 registros para controle de memória
- **Índices** — `id_terceirizado` e `cpf` indexados na camada Gold via post-hook do dbt

## 3. Estrutura de Arquivos

```
api/
├── main.py         # Inicialização FastAPI + health check (GET /)
├── config.py       # Configurações de ambiente (Pydantic BaseSettings)
├── database.py     # Conexão DuckDB via S3 (Singleton + httpfs)
├── schemas.py      # Modelos Pydantic (request/response)
└── routes.py       # Todos os endpoints (listagem, detalhe, filtros, análises)
```

## 4. Endpoints

### Obrigatórios (Requisito do Desafio)

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/terceirizados/` | Listagem paginada com `page` e `page_size` |
| `GET` | `/terceirizados/{id}` | Detalhes completos de um terceirizado |

### Filtros (Diferencial)

O endpoint de listagem aceita filtros opcionais via query parameters:

| Parâmetro | Tipo | Exemplo |
|---|---|---|
| `orgao` | string | `?orgao=MEC` |
| `cnpj` | string | `?cnpj=06311155000125` |
| `mes_referencia` | date | `?mes_referencia=2024-01-01` |

Os filtros são **combináveis** e utilizam queries parametrizadas (proteção contra SQL Injection).

### Endpoints Analíticos (Diferencial)

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/terceirizados/estatisticas` | Agregações: total de registros, órgãos, empresas, média salarial e período |
| `GET` | `/terceirizados/orgaos` | Lista de órgãos com contagem de terceirizados por órgão |

### Health Check

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/` | Status da API + link para documentação Swagger |

## 5. Estratégia de Cache

Utiliza `cachetools.TTLCache` com chaves baseadas nos parâmetros da requisição:

```
cache_key = f"list_{page}_{page_size}_{orgao}_{cnpj}_{mes_referencia}"
```

- **Maxsize**: 200 entradas
- **TTL**: Configurável via variável de ambiente `CACHE_EXPIRE_SECONDS`
- **Invalidação**: Automática por expiração temporal

## 6. Segurança

- **Queries parametrizadas** — Todos os endpoints usam `?` placeholders, eliminando SQL Injection
- **Validação Pydantic** — Tipos e limites validados automaticamente (`page >= 1`, `page_size <= 100`)
- **Credenciais isoladas** — Nenhuma credencial hardcoded; tudo via variáveis de ambiente

## 7. Documentação Interativa

A API gera documentação automática via FastAPI:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 8. Observabilidade (OpenTelemetry)

A API é instrumentada com **OpenTelemetry** para tracing distribuído. Cada request gera traces visíveis no Jaeger UI (`http://localhost:16686`), incluindo spans customizados para as queries DuckDB.

> Para detalhes completos sobre a configuração, consulte [Observabilidade](Observabilidade.md).

---
> Para detalhes sobre o pipeline de processamento, consulte [Arquitetura ELT Workflow](Arquitetura%20ELT%20Workflow.md).

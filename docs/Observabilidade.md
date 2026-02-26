# Observabilidade — OpenTelemetry

Instrumentação de tracing distribuído na API REST via **OpenTelemetry**, com visualização de traces no **Jaeger**.

---

## Arquitetura

```
FastAPI (auto-instrumentado)
       ↓  OTLP/HTTP (:4318)
   Jaeger (all-in-one)
       ↓
   Jaeger UI (:16686)
```

A instrumentação funciona em duas camadas:

| Camada | O que captura | Como |
|---|---|---|
| **Auto-instrumentação** | Cada request HTTP (método, rota, status, latência) | `FastAPIInstrumentor` — automático |
| **Spans customizados** | Queries DuckDB (operação, parâmetros, total de resultados) | `tracer.start_as_current_span()` em `routes.py` |

---

## Estrutura de Arquivos

```
api/
├── telemetry.py     # Configuração OTel (TracerProvider, exporter, instrumentação)
├── config.py        # Variáveis OTEL_ENABLED, OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT
├── main.py          # Inicialização: setup_telemetry(app) + shutdown via lifespan
└── routes.py        # Spans customizados por endpoint (duckdb.query)
```

O módulo `telemetry.py` centraliza toda a configuração e expõe duas funções:
- `setup_telemetry(app)` — Chamada na inicialização
- `shutdown_telemetry(provider)` — Chamada no shutdown (flush de spans pendentes)

---

## Configuração

| Variável | Padrão | Descrição |
|---|---|---|
| `OTEL_ENABLED` | `false` | Ativa/desativa o tracing |
| `OTEL_SERVICE_NAME` | `terceirizados-api` | Nome do serviço nos traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://jaeger:4318` | Endpoint do coletor OTLP |

No `docker-compose.yml`, o serviço `api` já define `OTEL_ENABLED=true` automaticamente.
Para desenvolvimento local sem Docker, basta deixar `OTEL_ENABLED=false` no `.env`.

---

## Como Visualizar Traces

1. Suba o stack: `docker-compose up --build -d`
2. Acesse o Jaeger UI: **http://localhost:16686**
3. Faça requests à API:
   ```bash
   curl http://localhost:8000/terceirizados/?page=1&page_size=5
   curl http://localhost:8000/terceirizados/1
   ```
4. No Jaeger, selecione o serviço **`terceirizados-api`** e clique **Find Traces**

Cada trace mostra:
- **Span raiz**: request HTTP (rota, método, status code, duração total)
- **Span filho**: `duckdb.query` com atributos `db.operation`, `db.result_count`, `query.page`, etc.

---

## Decisões de Design

| Decisão | Justificativa |
|---|---|
| Módulo separado (`telemetry.py`) | Isolamento — o código de negócio não conhece detalhes de observabilidade |
| Ativação condicional | Zero overhead em ambientes sem Jaeger; sem erros se o coletor estiver offline |
| Jaeger all-in-one (1 container) | Simplicidade — substitui stack Jaeger + OTel Collector + storage |
| OTLP via HTTP | Menor footprint que gRPC; sem necessidade de `grpcio` no projeto |
| Spans somente na API | O Prefect Server já fornece logs e tracking de tasks nativamente |

---

> Para detalhes sobre endpoints e cache, consulte [Arquitetura da API REST](API%20Architecture.md).
> Para detalhes sobre o pipeline ELT, consulte [Arquitetura ELT Workflow](Arquitetura%20ELT%20Workflow.md).

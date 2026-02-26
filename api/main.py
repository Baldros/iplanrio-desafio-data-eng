from contextlib import asynccontextmanager
from fastapi import FastAPI
from routes import router
from config import settings
from telemetry import setup_telemetry, shutdown_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação."""
    yield
    # Shutdown: flush de spans pendentes
    shutdown_telemetry(_otel_provider)


app = FastAPI(
    title="API de Terceirizados - IPLANRIO",
    description="API para consulta de dados da camada Ouro do pipeline de Terceirizados federais.",
    version="1.0.0",
    lifespan=lifespan,
)

# OpenTelemetry — instrumentação condicional
_otel_provider = setup_telemetry(app)

# Rotas
app.include_router(router)

@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "message": "API de Terceirizados IPLANRIO rodando com sucesso.",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.API_PORT)

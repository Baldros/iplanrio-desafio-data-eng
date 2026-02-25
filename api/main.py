from fastapi import FastAPI
from routes import router
from config import settings

app = FastAPI(
    title="API de Terceirizados - IPLANRIO",
    description="API para consulta de dados da camada Ouro do pipeline de Terceirizados federais.",
    version="1.0.0",
)

# Adiciona as rotas
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

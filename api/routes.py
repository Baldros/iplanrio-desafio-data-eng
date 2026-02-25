from fastapi import APIRouter, HTTPException, Query
from database import db_manager
from schemas import TerceirizadoFull, PaginatedResponse
from config import settings

# Usaremos um cache em memória simples para cumprir o requisito do desafio
from cachetools import TTLCache
cache = TTLCache(maxsize=100, ttl=settings.CACHE_EXPIRE_SECONDS)

router = APIRouter(prefix="/terceirizados", tags=["Terceirizados"])

@router.get("/", response_model=PaginatedResponse)
def list_terceirizados(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    """
    Retorna a lista completa de terceirizados com paginação.
    """
    cache_key = f"list_{page}_{page_size}"
    if cache_key in cache:
        return cache[cache_key]

    try:
        conn = db_manager.get_connection()
        offset = (page - 1) * page_size
        # Busca total de registros
        total = conn.execute("SELECT count(*) FROM gold_db.terceirizados_gold").fetchone()[0]
        
        # Busca registros paginados
        query = f"""
            SELECT id_terceirizado, orgao_superior_sigla, cnpj, cpf
            FROM gold_db.terceirizados_gold
            LIMIT {page_size} OFFSET {offset}
        """
        results = conn.execute(query).fetchall()
        
        column_names = [d[0] for d in conn.description]
        items = [dict(zip(column_names, row)) for row in results]
        
        response = PaginatedResponse(
            total_count=total,
            page=page,
            page_size=page_size,
            items=items
        )
        
        cache[cache_key] = response
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar banco: {e}")

@router.get("/{id_terceirizado}", response_model=TerceirizadoFull)
def get_terceirizado(id_terceirizado: str):
    """
    Retorna os detalhes de um terceirizado específico identificado pelo seu ID.
    """
    cache_key = f"detail_{id_terceirizado}"
    if cache_key in cache:
        return cache[cache_key]

    try:
        conn = db_manager.get_connection()
        query = """
            SELECT *
            FROM gold_db.terceirizados_gold
            WHERE id_terceirizado = ?
        """
        result = conn.execute(query, [id_terceirizado]).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Terceirizado não encontrado")
            
        column_names = [d[0] for d in conn.description]
        item = dict(zip(column_names, result))
        
        cache[cache_key] = item
        return item
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar banco: {e}")

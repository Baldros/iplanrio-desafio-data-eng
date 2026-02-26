from fastapi import APIRouter, HTTPException, Query
from database import db_manager
from schemas import TerceirizadoFull, PaginatedResponse, EstatisticasResponse, OrgaoItem
from config import settings
from typing import Optional

# Cache em memória simples para otimizar requisições frequentes
from cachetools import TTLCache
cache = TTLCache(maxsize=200, ttl=settings.CACHE_EXPIRE_SECONDS)

# OpenTelemetry — tracer para spans de queries DuckDB
from opentelemetry import trace
tracer = trace.get_tracer("terceirizados.routes")

router = APIRouter(prefix="/terceirizados", tags=["Terceirizados"])

# =====================================================================
# Endpoints auxiliares (devem vir ANTES das rotas com path params)
# =====================================================================

@router.get("/estatisticas", response_model=EstatisticasResponse, tags=["Análises"])
def get_estatisticas():
    """
    Retorna estatísticas agregadas sobre os terceirizados:
    total de registros, total de órgãos, média salarial, etc.
    """
    cache_key = "estatisticas"
    if cache_key in cache:
        return cache[cache_key]

    try:
        conn = db_manager.get_connection()
        with tracer.start_as_current_span("duckdb.query", attributes={"db.system": "duckdb", "db.operation": "estatisticas"}):
            query = """
                SELECT
                    COUNT(*) AS total_terceirizados,
                    COUNT(DISTINCT orgao_superior_sigla) AS total_orgaos,
                    COUNT(DISTINCT cnpj) AS total_empresas,
                    ROUND(AVG(salario_mensal_valor), 2) AS media_salarial,
                    ROUND(AVG(custo_mensal_valor), 2) AS media_custo,
                    MIN(mes_referencia_data) AS periodo_inicio,
                    MAX(mes_referencia_data) AS periodo_fim
                FROM gold_db.terceirizados_gold
            """
            result = conn.execute(query).fetchone()
            column_names = [d[0] for d in conn.description]
            stats = dict(zip(column_names, result))

        cache[cache_key] = stats
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar banco: {e}")


@router.get("/orgaos", response_model=list[OrgaoItem], tags=["Análises"])
def list_orgaos():
    """
    Retorna a lista de órgãos disponíveis com contagem de terceirizados.
    Útil para explorar os dados e alimentar filtros no frontend.
    """
    cache_key = "orgaos"
    if cache_key in cache:
        return cache[cache_key]

    try:
        conn = db_manager.get_connection()
        with tracer.start_as_current_span("duckdb.query", attributes={"db.system": "duckdb", "db.operation": "orgaos"}):
            query = """
                SELECT
                    orgao_superior_sigla AS sigla,
                    MAX(orgao_nome) AS nome,
                    COUNT(*) AS total_terceirizados
                FROM gold_db.terceirizados_gold
                WHERE orgao_superior_sigla IS NOT NULL
                GROUP BY orgao_superior_sigla
                ORDER BY total_terceirizados DESC
            """
            results = conn.execute(query).fetchall()
            column_names = [d[0] for d in conn.description]
            items = [dict(zip(column_names, row)) for row in results]

        cache[cache_key] = items
        return items

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar banco: {e}")


# =====================================================================
# Endpoints principais
# =====================================================================

@router.get("/", response_model=PaginatedResponse)
def list_terceirizados(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    orgao: Optional[str] = Query(None, description="Filtrar por sigla do órgão superior"),
    cnpj: Optional[str] = Query(None, description="Filtrar por CNPJ da empresa"),
    mes_referencia: Optional[str] = Query(None, description="Filtrar por data de referência (YYYY-MM-DD)")
):
    """
    Retorna a lista de terceirizados com paginação e filtros opcionais.
    """
    cache_key = f"list_{page}_{page_size}_{orgao}_{cnpj}_{mes_referencia}"
    if cache_key in cache:
        return cache[cache_key]

    try:
        conn = db_manager.get_connection()
        offset = (page - 1) * page_size

        # Construção dinâmica de filtros com queries parametrizadas
        where_clauses = []
        params = []

        if orgao:
            where_clauses.append("orgao_superior_sigla = ?")
            params.append(orgao)
        if cnpj:
            where_clauses.append("cnpj = ?")
            params.append(cnpj)
        if mes_referencia:
            where_clauses.append("mes_referencia_data = ?")
            params.append(mes_referencia)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        with tracer.start_as_current_span("duckdb.query", attributes={
            "db.system": "duckdb",
            "db.operation": "list_terceirizados",
            "query.page": page,
            "query.page_size": page_size,
            "query.has_filters": bool(where_clauses),
        }):
            # Total de registros (com filtro)
            count_query = f"SELECT count(*) FROM gold_db.terceirizados_gold {where_sql}"
            total = conn.execute(count_query, params).fetchone()[0]

            # Registros paginados (com filtro)
            query = f"""
                SELECT id_terceirizado, orgao_superior_sigla, cnpj, cpf
                FROM gold_db.terceirizados_gold
                {where_sql}
                LIMIT ? OFFSET ?
            """
            results = conn.execute(query, params + [page_size, offset]).fetchall()

            column_names = [d[0] for d in conn.description]
            items = [dict(zip(column_names, row)) for row in results]

            # Registra total de resultados no span
            span = trace.get_current_span()
            span.set_attribute("db.result_count", total)

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
        with tracer.start_as_current_span("duckdb.query", attributes={
            "db.system": "duckdb",
            "db.operation": "get_terceirizado",
            "query.id": id_terceirizado,
        }):
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

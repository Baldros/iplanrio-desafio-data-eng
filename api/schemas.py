from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Union
from datetime import date

class TerceirizadoBase(BaseModel):
    """Campos retornados no endpoint de listagem /terceirizados (conforme README)."""
    id_terceirizado: int
    orgao_superior_sigla: Optional[str] = None
    cnpj: Optional[str] = None
    cpf: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class TerceirizadoFull(TerceirizadoBase):
    """Todos os campos da camada Ouro — retornados no endpoint /terceirizados/{id}."""
    terceirizado_nome: Optional[str] = None
    categoria_profissional_nome: Optional[str] = None
    escolaridade_nome: Optional[str] = None
    jornada_quantidade: Optional[int] = None
    salario_mensal_valor: Optional[float] = None
    custo_mensal_valor: Optional[float] = None
    empresa_razao_social_nome: Optional[str] = None
    contrato_numero: Optional[str] = None
    orgao_sigla: Optional[str] = None
    orgao_nome: Optional[str] = None
    orgao_codigo_siafi: Optional[str] = None
    orgao_codigo_siape: Optional[str] = None
    unidade_gestora_codigo: Optional[str] = None
    unidade_gestora_nome: Optional[str] = None
    unidade_gestora_sigla: Optional[str] = None
    unidade_prestacao_nome: Optional[str] = None
    mes_carga_numero: Optional[int] = None
    mes_carga_nome: Optional[str] = None
    ano_carga: Optional[int] = None
    mes_referencia_data: Optional[date] = None

class PaginatedResponse(BaseModel):
    total_count: int
    page: int
    page_size: int
    items: List[TerceirizadoBase]

class EstatisticasResponse(BaseModel):
    """Estatísticas agregadas sobre os terceirizados."""
    total_terceirizados: int
    total_orgaos: int
    total_empresas: int
    media_salarial: Optional[float] = None
    media_custo: Optional[float] = None
    periodo_inicio: Optional[date] = None
    periodo_fim: Optional[date] = None

class OrgaoItem(BaseModel):
    """Órgão com contagem de terceirizados."""
    sigla: str
    nome: Optional[str] = None
    total_terceirizados: int

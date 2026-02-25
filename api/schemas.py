from pydantic import BaseModel, ConfigDict
from typing import List, Optional

class TerceirizadoBase(BaseModel):
    # Campos obrigatórios no endpoint de listagem conforme README
    id_terceirizado: str
    orgao_superior_sigla: Optional[str] = None
    cnpj: Optional[str] = None
    cpf: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class TerceirizadoFull(TerceirizadoBase):
    # Todos os campos da camada ouro para o endpoint de detalhe
    terceirizado_nome: Optional[str] = None
    categoria_profissional_nome: Optional[str] = None
    escolaridade_nome: Optional[str] = None
    jornada_quantidade: Optional[str] = None
    salario_mensal_valor: Optional[float] = None
    custo_mensal_valor: Optional[float] = None
    empresa_razao_social_nome: Optional[str] = None
    contrato_numero: Optional[str] = None
    orgao_sigla: Optional[str] = None
    orgao_nome: Optional[str] = None
    unidade_gestora_nome: Optional[str] = None
    mes_referencia: Optional[str] = None

class PaginatedResponse(BaseModel):
    total_count: int
    page: int
    page_size: int
    items: List[TerceirizadoBase]

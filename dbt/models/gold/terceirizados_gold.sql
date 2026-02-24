-- models/gold/terceirizados_gold.sql

{{ config(
    post_hook=[
        "CREATE INDEX IF NOT EXISTS idx_terceirizado_id ON {{ this }} (id_terceirizado);",
        "CREATE INDEX IF NOT EXISTS idx_terceirizado_cpf ON {{ this }} (cpf);"
    ]
) }}

SELECT
    id_terceirizado,
    orgao_superior_sigla,
    cnpj,
    cpf,
    terceirizado_nome,
    categoria_profissional_nome,
    escolaridade_nome,
    jornada_quantidade,
    salario_mensal_valor,
    custo_mensal_valor,
    empresa_razao_social_nome,
    contrato_numero,
    orgao_sigla,
    orgao_nome,
    unidade_gestora_nome,
    mes_referencia_data AS mes_referencia

FROM {{ source('silver', 'terceirizados_silver') }}

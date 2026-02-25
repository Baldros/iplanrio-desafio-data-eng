-- models/gold/terceirizados_gold.sql

{{ config(
    materialized='incremental',
    unique_key=['id_terceirizado', 'mes_referencia_data'],
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
    orgao_codigo_siafi,
    orgao_codigo_siape,
    unidade_gestora_codigo,
    unidade_gestora_nome,
    unidade_gestora_sigla,
    unidade_prestacao_nome,
    mes_carga_numero,
    mes_carga_nome,
    ano_carga,
    mes_referencia_data

FROM {{ source('silver', 'terceirizados_silver') }}

{% if is_incremental() %}
WHERE mes_referencia_data > (SELECT COALESCE(MAX(mes_referencia_data), '1900-01-01') FROM {{ this }})
{% endif %}

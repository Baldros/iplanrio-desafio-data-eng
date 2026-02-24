
  
    
    

    create  table
      "terceirizados-gold"."main"."terceirizados_gold__dbt_tmp"
  
    as (
      -- models/gold/terceirizados_gold.sql



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

FROM "silver"."main"."terceirizados_silver"
    );
  
  
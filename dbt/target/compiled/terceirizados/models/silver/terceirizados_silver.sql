-- models/silver/terceirizados_silver.sql
SELECT
    -- Chave primária primeiro
    TRY_CAST(id_terc AS INTEGER)                                                AS id_terceirizado,

    -- Dados do terceirizado
    nr_cpf                                                                      AS cpf,
    nm_terceirizado                                                             AS terceirizado_nome,
    nm_categoria_profissional                                                   AS categoria_profissional_nome,
    nm_escolaridade                                                             AS escolaridade_nome,
    TRY_CAST(nr_jornada AS INTEGER)                                             AS jornada_quantidade,
    ROUND(TRY_CAST(REPLACE(vl_mensal_salario, ',', '.') AS DOUBLE), 2)         AS salario_mensal_valor,
    ROUND(TRY_CAST(REPLACE(vl_mensal_custo,   ',', '.') AS DOUBLE), 2)         AS custo_mensal_valor,

    -- Dados da empresa
    nr_cnpj                                                                     AS cnpj,
    nm_razao_social                                                             AS empresa_razao_social_nome,
    nr_contrato                                                                 AS contrato_numero,

    -- Dados do órgão e unidade gestora
    sg_orgao_sup_tabela_ug                                                      AS orgao_superior_sigla,
    sg_orgao                                                                    AS orgao_sigla,
    nm_orgao                                                                    AS orgao_nome,
    cd_orgao_siafi                                                              AS orgao_codigo_siafi,
    cd_orgao_siape                                                              AS orgao_codigo_siape,
    cd_ug_gestora                                                               AS unidade_gestora_codigo,
    nm_ug_tabela_ug                                                             AS unidade_gestora_nome,
    sg_ug_gestora                                                               AS unidade_gestora_sigla,
    nm_unidade_prestacao                                                        AS unidade_prestacao_nome,

    -- Metadados de carga (por último, conforme o manual)
    TRY_CAST(num_mes_carga AS INTEGER)                                          AS mes_carga_numero,
    mes_carga                                                                   AS mes_carga_nome,
    TRY_CAST(ano_carga AS INTEGER)                                              AS ano_carga,
    MAKE_DATE(
        TRY_CAST(ano_carga AS INTEGER),
        TRY_CAST(num_mes_carga AS INTEGER),
        1
    )                                                                           AS mes_referencia_data

FROM "bronze"."main"."terceirizados"
WHERE nr_cpf IS NOT NULL
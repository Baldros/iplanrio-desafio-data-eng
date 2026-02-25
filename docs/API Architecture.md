# Arquitetura da API REST - Desafio IPLANRIO

Este documento detalha a arquitetura técnica da API desenvolvida para expor os dados da camada Ouro do pipeline de Terceirizados.

## 1. Visão Geral
A API é construída utilizando o framework **FastAPI**, escolhido por sua performance, validação automática via Pydantic e documentação nativa (Swagger/OpenAPI). A arquitetura segue princípios de separação de responsabilidades para garantir manutenibilidade e portabilidade.

## 2. Pilares de Design

### 2.1 Agnosticismo de Ambiente
A API não possui dependência direta de arquivos físicos locais para os dados. Ela utiliza a capacidade do DuckDB de ler bancos de dados hospedados em buckets S3 (ou MinIO) através da extensão `httpfs`.
- **Configuração**: Através de variáveis de ambiente (`S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, etc.).
- **Comportamento**: Se o endpoint estiver configurado, o DuckDB conecta via HTTP; caso contrário, assume o comportamento padrão da AWS ou local.

### 2.2 Performance e Escalabilidade
- **DuckDB como Motor**: Consultas analíticas rápidas diretamente no formato DuckDB.
- **Cache**: Implementação de um mecanismo de cache (ex: `fastapi-cache2` ou cache em memória) para evitar re-consultas ao storage para os mesmos filtros.
- **Paginação**: Obrigatória no endpoint listagem para evitar sobrecarga de memória e rede.

## 3. Estrutura de Pastas Proposta

```text
api/
├── main.py             # Inicialização e middlewares
├── config.py           # Configurações de ambiente e segredos
├── database.py         # Conexão e pooling do DuckDB
├── schemas.py          # Modelos Pydantic (Request/Response)
├── routes/             # Definição dos endpoints
│   └── terceirizados.py
├── services/           # Lógica de negócio e queries SQL
└── tests/              # Testes de integração
```

## 4. Endpoints

### `GET /terceirizados`
- **Descrição**: Lista resumida dos terceirizados.
- **Filtros/Paginação**: `page`, `page_size`.
- **Campos**: `id_terceirizado`, `sigla_orgao_superior`, `cnpj_empresa`, `cpf_terceirizado`.

### `GET /terceirizados/{id}`
- **Descrição**: Detalhes completos de um registro.
- **Retorno**: Todos os campos da camada Ouro.

## 5. Estratégia de Caching
Será utilizado um cache baseado em tempo (TTL) para os resultados das consultas. Isso reduz o custo de saída de dados (egress) do S3 e melhora o tempo de resposta para usuários finais.

## 6. Padronização (Guia de Estilo IPLANRIO)
A API refletirá os nomes de colunas já transformados pelo dbt na camada Ouro, seguindo o manual de estilo da IPLANRIO (ex: uso de prefixos como `nm_`, `cd_`, `id_`).

---
> Documentação gerada como parte do planejamento técnico do desafio.

## O que é uma arquitetura medallion?

Uma arquitetura medallion é um padrão de design de dados usado para organizar logicamente os dados em um lakehouse, com o objetivo de melhorar incremental e progressivamente a estrutura e a qualidade dos dados à medida que eles fluem por cada camada da arquitetura (de tabelas Bronze ⇒ Silver ⇒ Gold). Arquiteturas medallion também são às vezes chamadas de arquiteturas “multi-hop”.

---

## Construindo pipelines de dados confiáveis e performáticos com Delta Lake

### Veja mais conteúdos

eb big book of data engineering 4th ed ty tn
**Big Book of Data Engineering**

Aprenda as melhores práticas essenciais de engenharia de dados.

**Leia agora**

---

**Data Intelligence Platform**
Explore a Data Intelligence Platform

Acelere ETL, data warehousing, BI e IA.

**Leia agora**

---

**Comece com ETL**
Comece com ETL

Aprenda sobre pipelines de ETL com este guia técnico da O’Reilly.

**Baixe agora**

---

## Construindo pipelines de dados com arquitetura medallion

A Databricks fornece ferramentas como Spark Declarative Pipelines que permitem aos usuários construir instantaneamente pipelines de dados com tabelas Bronze, Silver e Gold a partir de apenas algumas linhas de código. Além disso, com tabelas de streaming e views materializadas, os usuários podem criar pipelines Lakeflow em streaming construídos sobre o Apache Spark™️ Structured Streaming que são atualizados e renovados incrementalmente. Para mais detalhes, consulte a documentação da Databricks sobre como combinar tabelas de streaming e views materializadas em um único pipeline.

---

## Camada Bronze (dados brutos)

A camada Bronze é onde todos os dados provenientes de sistemas externos são armazenados. As estruturas das tabelas nessa camada correspondem às estruturas das tabelas do sistema de origem “como estão” (“as-is”), juntamente com colunas adicionais de metadados que capturam data/hora de carga, ID do processo etc. O foco nessa camada é a rápida captura de mudanças (Change Data Capture) e a capacidade de fornecer um arquivo histórico da fonte (armazenamento frio), linhagem de dados, auditabilidade e reprocessamento, se necessário, sem reler os dados do sistema de origem.

---

## Camada Silver (dados limpos e conformados)

Na camada Silver do lakehouse, os dados da camada Bronze são combinados, mesclados, conformados e limpos (“just-enough”) para que a camada Silver possa fornecer uma “visão corporativa” (“Enterprise view”) de todas as principais entidades, conceitos e transações do negócio (por exemplo, clientes mestres, lojas, transações sem duplicação e tabelas de referência cruzada).

A camada Silver reúne dados de diferentes fontes em uma visão corporativa e permite análises self-service para relatórios ad-hoc, análises avançadas e machine learning. Ela serve como fonte para Analistas Departamentais, Engenheiros de Dados e Cientistas de Dados criarem projetos e análises adicionais para responder a problemas de negócio por meio de projetos de dados corporativos e departamentais na camada Gold.

No paradigma de engenharia de dados em lakehouse, normalmente segue-se a metodologia ELT em vez de ETL — o que significa que apenas transformações mínimas ou “just-enough” e regras de limpeza de dados são aplicadas durante o carregamento na camada Silver. Prioriza-se velocidade e agilidade para ingerir e disponibilizar os dados no data lake, enquanto muitas transformações complexas e regras de negócio específicas de projetos são aplicadas ao carregar os dados da camada Silver para a Gold. Do ponto de vista de modelagem de dados, a camada Silver possui modelos mais próximos da 3ª Forma Normal. Modelos do tipo Data Vault, otimizados para escrita, podem ser utilizados nessa camada.

---

## Camada Gold (tabelas curadas em nível de negócio)

Os dados na camada Gold do lakehouse são normalmente organizados em bancos de dados “específicos de projeto” prontos para consumo. A camada Gold é voltada para relatórios e utiliza modelos de dados mais desnormalizados e otimizados para leitura, com menos junções. A camada final de transformações de dados e regras de qualidade é aplicada aqui. A camada final de apresentação de projetos como Customer Analytics, Product Quality Analytics, Inventory Analytics, Customer Segmentation, Product Recommendations, Marketing/Sales Analytics etc. se encaixa nesta camada. Observamos muitos modelos de dados baseados em star schema no estilo Kimball ou Data Marts no estilo Inmon nesta camada Gold do lakehouse.

---

Assim, é possível ver que os dados são curados à medida que se movem pelas diferentes camadas de um lakehouse. Em alguns casos, também vemos que muitos Data Marts e EDWs da pilha tecnológica tradicional baseada em RDBMS são ingeridos no lakehouse, permitindo que, pela primeira vez, as empresas realizem análises avançadas e machine learning “pan-EDW” — algo que não era possível ou era proibitivamente caro em uma arquitetura tradicional (por exemplo, dados de IoT/Manufatura combinados com dados de Vendas e Marketing para análise de defeitos, ou dados de genômica em saúde e mercados clínicos EMR/HL7 combinados com dados de sinistros financeiros para criar um Healthcare Data Lake voltado para análises mais rápidas e eficazes no cuidado ao paciente).

---

## Benefícios de uma arquitetura lakehouse

Modelo de dados simples
Fácil de entender e implementar
Permite ETL incremental
Permite recriar suas tabelas a partir dos dados brutos a qualquer momento
Transações ACID, time travel

---

## Uma introdução rápida aos lakehouses

Um lakehouse é um paradigma de arquitetura de plataforma de dados que combina as melhores características de data lakes e data warehouses. Um lakehouse moderno é uma plataforma de dados altamente escalável e performática que hospeda tanto conjuntos de dados brutos quanto preparados para consumo rápido pelo negócio e para impulsionar insights e decisões avançadas. Ele elimina silos de dados e permite acesso contínuo e seguro aos dados por usuários autorizados em toda a empresa, em uma única plataforma.

---

**Arquitetura da Plataforma Lakehouse da Databricks**

---

## Arquitetura medallion e data mesh

A arquitetura Medallion é compatível com o conceito de data mesh. Tabelas Bronze e Silver podem ser combinadas em um formato “um-para-muitos”, o que significa que os dados de uma única tabela upstream podem ser usados para gerar múltiplas tabelas downstream.

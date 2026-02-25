"""
Módulo responsável pela aquisição de dados. Aqui estruturamos
toda a estratégia de scraping para extrair os dados da página
fornecida pelo desafio.
"""


# Dependências
import re
import io
import time
import zipfile
import requests
import polars as pl
from tqdm import tqdm
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sys

# Lista final com 25 colunas já considerando ano e mes inseridos ao final da extração
EXPECTED_COLUMNS = [
    'id_terc',
    'sg_orgao_sup_tabela_ug',
    'cd_ug_gestora',
    'nm_ug_tabela_ug',
    'sg_ug_gestora',
    'nr_contrato',
    'nr_cnpj',
    'nm_razao_social',
    'nr_cpf',
    'nm_terceirizado',
    'nm_categoria_profissional',
    'nm_escolaridade',
    'nr_jornada',
    'nm_unidade_prestacao',
    'vl_mensal_salario',
    'vl_mensal_custo',
    'Num_Mes_Carga',
    'Mes_Carga',
    'Ano_Carga',
    'sg_orgao',
    'nm_orgao',
    'cd_orgao_siafi',
    'cd_orgao_siape'
]

class ScrapingClient:
    """
    Classe responsável por extrair os metadados da página de Terceirizados do 
    Governo Federal via HTML (BeautifulSoup). 
    Realiza o parsing das tags para encontrar todos os downloads e cuida do 
    download do CSV, convertendo diretamente para DataFrame Polars em memória.
    """
    
    def __init__(self, url: str):
        self.url = url
        
    def get_links(self) -> dict:
        """
        Acessa a página oficial e vasculha as tags de <h3> e <ul> para mapear 
        cada ano e seus respectivos meses de arquivos disponíveis para download.
        Retorna um dicionário hierárquico no formato: { '2025': { 'Janeiro': 'http...', ... } }
        """
        print(f"[Scraping] Acessando {self.url}")
        
        response = requests.get(self.url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        dados = {}
        
        # O padrão da página do governo agrupa os arquivos colocando o ano numa tag <h3>
        for h3 in soup.find_all("h3"):
            texto = h3.get_text(strip=True)
            
            # Verifica se o texto do H3 é exatamente 4 dígitos numéricos (o ano) r"^\d{4}$"
            if re.match(r"^\d{4}$", texto):
                ano = texto
                dados[ano] = {}
                
                # Os meses ficam numa lista não ordenada (<ul>) posicionada logo após o <h3> do ano
                ul = h3.find_next_sibling("ul")
                if ul:
                    # Encontra todas as tags de link (âncoras <a>) dentro da lista
                    for a in ul.find_all("a", href=True):
                        # Pega o texto limpo da tag que tem o nome escrito do Mês
                        mes = a.get_text(strip=True).title()
                        
                        # urljoin previne erros caso os links do gov formatem "/arquivo.csv" sem a base URL
                        link = urljoin(self.url, a["href"])
                        
                        dados[ano][mes] = link
                        
        print(f"[Scraping] Mapeamento concluído. Anos encontrados: {list(dados.keys())}")
        return dados

    def download_data(self, csv_url: str, ano: str, mes: str, max_retries: int = 5) -> pl.DataFrame:
        """
        Faz o download do CSV pela URL especificada e converte para um 
        DataFrame colunar moderno usando o Polars. Lida elegantemente 
        com arquivos compactados (.zip) se necessário. Incorpora estratégia
        de retry com backoff exponencial para falhas de conexão (IncompleteRead).
        """        
        content = None
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(csv_url, timeout=120)
                response.raise_for_status()
                content = response.content
                break # Sucesso, prossegue para conversão
            except Exception as e:
                print(f"[Scraping] Tivemos um erro na conexão para {ano}-{mes} (Tentativa {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    print(f"[Scraping] Limite de tentativas atingido para {ano}-{mes}. Abortando.")
                    raise e
                sleep_time = 2 ** attempt # 2, 4, 8, 16...
                print(f"[Scraping] Aguardando {sleep_time} segundos antes da próxima tentativa...")
                time.sleep(sleep_time)


        # O Polars consegue lidar com objetos de bytes diretamente.
        try:
            if csv_url.lower().endswith(".xlsx") or csv_url.lower().endswith(".xls"):
                df = pl.read_excel(io.BytesIO(content), has_header=False)
            elif zipfile.is_zipfile(io.BytesIO(content)):
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    nome = z.namelist()[0]
                    with z.open(nome) as f:
                        df = pl.read_csv(
                            f,
                            separator=";",
                            encoding="latin1", # Sites do governo frequentemente mandam planilhas compactadas ou em latin1
                            truncate_ragged_lines=True,
                            ignore_errors=True,
                            has_header=False,
                            infer_schema_length=0, # Ler tudo como string primeiro 
                        )
            else:
                df = pl.read_csv(
                    io.BytesIO(content),
                    separator=";",
                    encoding="latin1", # Sites do governo frequentemente mandam planilhas compactadas ou em latin1.
                    truncate_ragged_lines=True,
                    ignore_errors=True,
                    has_header=False,
                    infer_schema_length=0, # Ler tudo como string primeiro
                )

        except Exception as e:
            print(f"[Scraping] Falha ao processar {ano}-{mes}. Erro: {e}")
            raise e
            
        # Normalização de Cabeçalho
        if df.height > 0:
            # Pega o primeiro valor da primeira coluna para testar
            first_val = str(df[0, 0]).lower()
            
            # Se a primeira linha contiver nomes de colunas como id_terc, cpf, cnpj, descartamos (pois já temos EXPECTED_COLUMNS)
            # A lista fornecida tem 'id_terc'
            if 'id_terc' in first_val or 'id' in first_val:
                df = df.slice(1)
                
            # Verifica a quantide de colunas lidas vs mapeadas
            num_cols = df.width
            expected_num = len(EXPECTED_COLUMNS)
            
            if num_cols < expected_num:
                # Faltaram colunas (o csv talvez fosse muito quebrado). Adicionamos colunas null.
                for i in range(num_cols, expected_num):
                    df = df.with_columns(pl.lit(None).alias(f"column_{i}"))
                    
            elif num_cols > expected_num:
                # Vieram colunas fantasmas (ex: ;, no final das linhas CSV)
                df = df.select(df.columns[:expected_num])
            
            # Renomeia exatamente de acordo com nossa lista blindada!
            df.columns = EXPECTED_COLUMNS
            
            # Limpeza de caracteres estranhos (BOM) que vieram da leitura UTF-8 como Latin1
            # E remoção de espaços nas extremidades usando expressões de string do Polars
            df = df.with_columns(pl.all().cast(pl.Utf8).str.replace_all("ï»¿", "").str.strip_chars())
        
        # Usamos .with_columns para inserir/substituir o ano numérico e o respectivo mês como literais
        # e tipificar as colunas corretas.
        df_final = df.with_columns([
            pl.lit(int(ano)).alias("ano"),
            pl.lit(mes).alias("mes")
        ])
    
        return df_final

    def get_all_data(self) -> dict[str, dict[str, pl.DataFrame]]:
        """
        Orquestra o processo completo:
        1. Mapeia todos os links disponíveis.
        2. Faz download de cada arquivo.
        3. Retorna um dicionário hierárquico contendo os DataFrames:
           { '2025': { 'Janeiro': pl.DataFrame, ... }, ... }
        """

        links_dict = self.get_links()
        dados_completos = {}

        for ano, meses in tqdm(links_dict.items(), desc="Baixando dados..."):
            dados_completos[ano] = {}

            for mes, link in meses.items():
                try:
                    df = self.download_data(link, ano, mes)
                    dados_completos[ano][mes] = df
                except Exception as e:
                    print(f"[Scraping] Erro ao baixar {ano}-{mes}: {e}")
                    continue

        return dados_completos
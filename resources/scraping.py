"""
Módulo responsável pela aquisição de dados. Aqui estruturamos
toda a estratégia de scraping para extrair os dados da página
fornecida pelo desafio.
"""


# Dependências
import re
import io
import zipfile
import requests
import polars as pl
from tqdm import tqdm
from bs4 import BeautifulSoup
from urllib.parse import urljoin



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

    def download_data(self, csv_url: str, ano: str, mes: str) -> pl.DataFrame:
        """
        Faz o download do CSV pela URL especificada e converte para um 
        DataFrame colunar moderno usando o Polars. Lida elegantemente 
        com arquivos compactados (.zip) se necessário.
        """        
        response = requests.get(csv_url)
        response.raise_for_status()
        content = response.content

        # O Polars consegue lidar com objetos de bytes diretamente.
        try:
            if csv_url.lower().endswith(".xlsx") or csv_url.lower().endswith(".xls"):
                df = pl.read_excel(io.BytesIO(content))
            elif zipfile.is_zipfile(io.BytesIO(content)):
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    nome = z.namelist()[0]
                    with z.open(nome) as f:
                        df = pl.read_csv(
                            f,
                            separator=";",
                            encoding="latin1", # Sites do governo frequentemente mandam planilhas compactadas ou em latin1
                            truncate_ragged_lines=True,
                            ignore_errors=True
                        )
            else:
                df = pl.read_csv(
                    io.BytesIO(content),
                    separator=";",
                    encoding="latin1", # Sites do governo frequentemente mandam planilhas compactadas ou em latin1.
                    truncate_ragged_lines=True,
                    ignore_errors=True
                )
        except Exception as e:
            print(f"[Scraping] Falha ao processar {ano}-{mes}. Erro: {e}")
            raise e
        # Usamos .with_columns para inserir/substituir o ano numérico e o respectivo mês como literais
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
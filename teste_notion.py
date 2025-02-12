from notion_client import Client
import json
import requests
import datetime
import holidays
import time
import math

# Inicialize o client com seu token de integração
notion = Client(auth="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")

# ID do database que contém os cards (você encontra na URL do seu database)
database_id = "18f30ca2d8ff81ef947bf436db931bf2"

# 1. Consulta o database e recupera os cards
response = notion.databases.query(database_id=database_id)
pages = response.get("results", [])

def calculo_acao(indice):
    """
    Consulta o valor atual do ativo a partir da API da Brapi.

    Retorna:
        float: O valor de mercado atual (regularMarketPrice) do ativo.
    """
    # Nome do ativo; pode ser passado via parâmetro se necessário.
    indice = indice
    token = "e31ZprPcuG4qM1pWYHmeEp"  # Substitua pelo seu token válido

    # Monta a URL para consulta
    url = f"https://brapi.dev/api/quote/{indice}?token={token}"
    response = requests.get(url)
    data = response.json()

    # Extrai o valor de mercado atual do primeiro resultado
    regular_market_price = data['results'][0]['regularMarketPrice']

    return regular_market_price

def is_business_day(check_date):
    """
    Verifica se uma data específica é dia útil.
    
    Retorna:
        bool: True se for dia útil, False se for fim de semana ou feriado.
    """
    # Cria o dicionário de feriados para o Brasil no ano da data
    br = holidays.Brazil(years=[check_date.year])
    
    # Adiciona feriados que normalmente não rendem (ex.: Carnaval e Corpus Christi)
    br.update({
        datetime.date(2025, 3, 3): "Carnaval",
        datetime.date(2025, 3, 4): "Carnaval",
        datetime.date(2026, 2, 16): "Carnaval",
        datetime.date(2026, 2, 17): "Carnaval",
    })
    # Corpus Christi: em 2025, cai em 19 de junho.
    br[datetime.date(2025, 6, 19)] = "Corpus Christi"
    br[datetime.date(2026, 6, 4)] = "Corpus Christi"
    
    # Se for sábado (5) ou domingo (6), não é dia útil.
    if check_date.weekday() >= 5:
        return False
    
    # Se a data for feriado, também não é dia útil.
    if check_date in br:
        return False
    
    return True

def pegar_cdi_dia_anterior():
    """
    Busca e imprime os 10 registros mais recentes da taxa CDI usando a API do Banco Central.

    Observação:
        A API do BCB fornece os dados em formato JSON. Se a resposta estiver vazia,
        uma mensagem será exibida.
    """
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/10?formato=json"
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.HTTPError:
        print("Dado não encontrado, continuando.")
        dado = None
    except Exception as exc:
        print("Erro, parando a execução.")
        raise exc
    else:
        if response.text.strip() == "":
            print("Resposta vazia!")
            dado = None
        else:
            dado = json.loads(response.text)
        
    return dado[0]['valor']

def truncar_excel(d3, i1, casas_decimais):
    """
    Replica a função do Excel: =TRUNCAR(1+(D3*$I$1);15)
    
    Parâmetros:
        d3             - valor correspondente à célula D3
        i1             - valor correspondente à célula I1
        casas_decimais - número de casas decimais para truncar (padrão é 15)
        
    Retorna:
      O resultado de 1 + (d3 * i1) truncado para 'casas_decimais' casas decimais.
    """
    # Calcula a expressão: 1 + (D3 * I1)
    valor = 1 + ((d3) * i1)
    
    # Calcula o fator de multiplicação para preservar as casas decimais
    fator = 10 ** casas_decimais
    
    # Utiliza math.trunc para remover os dígitos extras
    valor_truncado = math.trunc(valor * fator) / fator
    return valor_truncado


if not pages:
    print("Nenhum card encontrado no database.")
    exit()

# Seleciona o primeiro card para o exemplo
for card in pages:
    props = card["properties"]

    tipo = props.get("Tipo", {}).get("select", {}).get("name")
    if tipo == "Ação":

        # 2. Extrai os valores necessários das propriedades
        # (Certifique-se de que os nomes abaixo batem exatamente com os do seu database.)
        preco_compra = props.get("Valor Aplicado", {}).get("number")
        quantidade = props.get("Quantidade", {}).get("number")
        indice = props.get("Indice", {}).get("rich_text", {})[0]['text']['content']
        valor_atual = float(calculo_acao(indice))

        # Verifica se os valores necessários estão definidos
        if preco_compra is None or quantidade is None or valor_atual is None:
            print("Alguma das propriedades numéricas não está definida. Verifique seu database.")

        else:
            # 3. Realiza os cálculos
            #rendimento = (valor_atual - preco_compra) * quantidade
            valor_investido = quantidade * preco_compra
            valor_atual_total = quantidade * valor_atual

            # Calcula o ganho total e o rendimento percentual
            ganho = valor_atual_total - valor_investido
            rendimento_percentual = (ganho / valor_investido) *100
            rendimento_percentual = round(rendimento_percentual, 2)
            rendimento_percentual = rendimento_percentual / 100
        
            # 4. Prepara o payload de atualização
            # Certifique-se de que as propriedades "total compra", "Rendimento" e "Rendimento atual"
            # são do tipo number (não fórmula) para que possam ser atualizadas.
            update_payload = {
                "Rendimento": {"number": rendimento_percentual},
                "Ganho": {"number": ganho},
                "Valor Atual":{"number":valor_atual}
            }

            # Atualiza o card com os novos valores
            updated_page = notion.pages.update(
                page_id=card["id"],
                properties=update_payload
            )
    
    if tipo == "LCA / LCI":
        data_hoje = datetime.date.today()
        if is_business_day(data_hoje):

            Valor_Aplicado = props.get("Valor Aplicado", {}).get("number")
            Taxa_aplica = props.get("Taxa de aplicação", {}).get("number")
            Taxa_acumulada = props.get("Taxa Acumulada", {}).get("number")
            Taxa_anterior = props.get("Taxa anterior", {}).get("number")

            while True:
                try:
                    C3 = int(pegar_cdi_dia_anterior())
                    break  # Sai do loop se a conversão for bem-sucedida
                except Exception as e:
                    print("Erro ao tentar obter o CDI:", e)
                    print("Tentando novamente...")
                    time.sleep(1)  # Aguarda 1 segundo antes de tentar novamente

            # Cálculo da taxa diária considerando 252 dias úteis no ano:
            taxa_diaria = (((C3 / 100) + 1) ** (1 / 252)) - 1

            # Arredondando para 8 casas decimais:
            resultado = round(taxa_diaria, 8)

            taxa_truncada = truncar_excel(resultado, Taxa_aplica, 15)

            if Taxa_acumulada == 1:
                update_payload = {
                "Taxa anterior": {"number": taxa_truncada},
                }

                # Atualiza o card com os novos valores
                updated_page = notion.pages.update(
                    page_id=card["id"],
                    properties=update_payload
                )
            else:
                
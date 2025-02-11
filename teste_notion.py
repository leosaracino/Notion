from notion_client import Client
import json
import requests
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
            exit()

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

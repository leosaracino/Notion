import requests


def calculo_ação():
    #Aqui vai entrar o nome do indice pelo notion
    indice = 'BOVA11'
    token = "e31ZprPcuG4qM1pWYHmeEp"  # Substitua pelo seu token válido

    url = f"https://brapi.dev/api/quote/{indice}?token={token}"
    response = requests.get(url)
    data = response.json()

    #valor de cada ativo p valor atual dele
    regular_market_price = data['results'][0]['regularMarketPrice']
    print(regular_market_price)

    return regular_market_price


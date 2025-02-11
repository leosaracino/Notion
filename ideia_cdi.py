import requests
"""
Consulta o valor atual do ativo a partir da API da Brapi.

Retorna:
    float: O valor de mercado atual (regularMarketPrice) do ativo.
"""
# Nome do ativo; pode ser passado via parâmetro se necessário.
indice = 'BOVA11'
token = "e31ZprPcuG4qM1pWYHmeEp"  # Substitua pelo seu token válido

# Monta a URL para consulta
url = f"https://brapi.dev/api/quote/{indice}?token={token}"
response = requests.get(url)
data = response.json()

# Extrai o valor de mercado atual do primeiro resultado
regular_market_price = data['results'][0]['regularMarketPrice']
print(regular_market_price)
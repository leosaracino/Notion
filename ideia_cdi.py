import requests
import json

"""
Busca e imprime os 10 registros mais recentes da taxa CDI usando a API do Banco Central.

Observação:
    A API do BCB fornece os dados em formato JSON. Se a resposta estiver vazia,
    uma mensagem será exibida.
"""
url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/10?formato=json"
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
    
print(dado)
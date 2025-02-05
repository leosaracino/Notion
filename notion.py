import requests
import datetime
import holidays

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

def calculo_fim_de_semana_e_feriado():
    # Cria o dicionário de feriados para o Brasil no ano de 2025
    br = holidays.Brazil(years=[2025])

    # Adiciona manualmente os feriados que afetam o rendimento dos CDBs:
    # Carnaval: normalmente os bancos não rendem na segunda e terça-feira de Carnaval.
    # Em 2025, considerando que quarta feira de cinzas é 05/03/2025, os feriados de Carnaval seriam:
    br.update({
        datetime.date(2025, 3, 3): "Carnaval",
        datetime.date(2025, 3, 4): "Carnaval",
    })
    # Corpus Christi: em 2025, cai em 19/06/2025
    br[datetime.date(2025, 6, 19)] = "Corpus Christi"

    def is_business_day(check_date):
        """Retorna True se a data for dia útil (não for fim de semana nem feriado), caso contrário, False."""
        # Se for sábado (weekday == 5) ou domingo (weekday == 6)
        if check_date.weekday() >= 5:
            return False
        # Se a data estiver entre os feriados
        if check_date in br:
            return False
        return True

    # Função para exibir o status de um dia informado
    def check_day_status(check_date):
        if is_business_day(check_date):
            print(f"{check_date} é dia útil.")
        else:
            if check_date in br:
                print(f"{check_date} é feriado: {br.get(check_date)}")
            else:
                print(f"{check_date} é fim de semana.")

    # Exemplo de uso:
    # Altere a data conforme necessário
    data_input = datetime.date(2025, 2, 8)
    check_day_status(data_input)


CDI = 'cdi'
URL = "https://brasilapi.com.br/api/taxas/v1/{CDI}"
url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4392/dados/ultimos/10?formato=json"
# Captando a taxa CDI do site do BCB
import json
try:
    response = requests.get(url=url)
    response.raise_for_status()
except requests.HTTPError as exc:
    print("Dado não encontrado, continuando.")
    cdi = None
except Exception as exc:
    print("Erro, parando a execução.")
    raise exc
else:
    dado = json.loads(response.text)#[-1]['valor']

print(dado)

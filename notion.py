import requests
import datetime
import holidays
import json

def calculo_acao():
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

    return regular_market_price


def calculo_fim_de_semana_e_feriado():
    """
    Verifica se uma data específica é dia útil, feriado ou fim de semana.

    Utiliza a biblioteca 'holidays' para obter os feriados oficiais do Brasil no ano de 2025
    e adiciona manualmente feriados que afetam o rendimento de investimentos (Carnaval e Corpus Christi).
    Exibe o status de uma data de exemplo.
    """
    # Cria o dicionário de feriados para o Brasil em 2025
    br = holidays.Brazil(years=[2025])

    # Adiciona feriados que normalmente não rendem (ex.: Carnaval e Corpus Christi)
    # Carnaval: em 2025, os bancos costumam não render na segunda e terça-feira de Carnaval.
    br.update({
        datetime.date(2025, 3, 3): "Carnaval",
        datetime.date(2025, 3, 4): "Carnaval",
        datetime.date(2026, 2, 16): "Carnaval",
        datetime.date(2026, 2, 17): "Carnaval",
    })
    # Corpus Christi: em 2025, cai em 19 de junho.
    br[datetime.date(2025, 6, 19)] = "Corpus Christi"
    br[datetime.date(2026, 6, 4)] = "Corpus Christi"

    def is_business_day(check_date):
        """
        Verifica se uma data é dia útil.

        Args:
            check_date (datetime.date): Data a ser verificada.

        Returns:
            bool: True se for dia útil, False se for fim de semana ou feriado.
        """
        # Se for sábado (5) ou domingo (6), retorna False.
        if check_date.weekday() >= 5:
            return False
        # Se a data estiver marcada como feriado
        if check_date in br:
            return False
        return True

    def check_day_status(check_date):
        """
        Imprime o status da data: dia útil, fim de semana ou feriado (com nome do feriado).

        Args:
            check_date (datetime.date): Data a ser verificada.
        """
        if is_business_day(check_date):
            print(f"{check_date} é dia útil.")
        else:
            if check_date in br:
                print(f"{check_date} é feriado: {br.get(check_date)}")
            else:
                print(f"{check_date} é fim de semana.")

    # Exemplo: verifica o status de 8 de fevereiro de 2025
    data_input = datetime.date(2025, 2, 8)
    check_day_status(data_input)


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


# # Exemplo de chamadas:
# if __name__ == "__main__":
#     valor_ativo = calculo_acao()
#     calculo_fim_de_semana_e_feriado()
#     pegar_cdi_dia_anterior()

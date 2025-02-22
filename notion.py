import datetime
import holidays
import json
import locale
import requests
import time
from decimal import Decimal, getcontext, ROUND_HALF_UP, ROUND_DOWN

from notion_client import Client

# ==============================
# Configurações Globais
# ==============================
NOTION_TOKEN = "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"
DATABASE_ID = "18f30ca2d8ff81ef947bf436db931bf2"
BRAPI_TOKEN = "e31ZprPcuG4qM1pWYHmeEp"

getcontext().prec = 30
locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

# Inicializa o client do Notion
notion = Client(auth=NOTION_TOKEN)


# ==============================
# Funções Auxiliares
# ==============================
def calculo_acao(indice: str) -> float:
    """
    Consulta o valor atual do ativo a partir da API da Brapi.

    Args:
        indice (str): O código do ativo.

    Returns:
        float: Valor de mercado atual do ativo.
    """
    url = f"https://brapi.dev/api/quote/{indice}?token={BRAPI_TOKEN}"
    response = requests.get(url)
    data = response.json()

    try:
        price = data['results'][0]['regularMarketPrice']
    except (KeyError, IndexError):
        raise ValueError("Dados inválidos recebidos da API Brapi")
    return float(price)


def is_business_day(check_date: datetime.date) -> bool:
    """
    Verifica se uma data é dia útil (desconsidera finais de semana e feriados).

    Args:
        check_date (datetime.date): Data a ser verificada.

    Returns:
        bool: True se for dia útil, caso contrário False.
    """
    br_holidays = holidays.Brazil(years=[check_date.year])
    # Adiciona feriados que normalmente não rendem (ex.: Carnaval e Corpus Christi)
    br_holidays.update({
        datetime.date(2025, 3, 3): "Carnaval",
        datetime.date(2025, 3, 4): "Carnaval",
        datetime.date(2026, 2, 16): "Carnaval",
        datetime.date(2026, 2, 17): "Carnaval",
    })
    # Corpus Christi
    br_holidays[datetime.date(2025, 6, 19)] = "Corpus Christi"
    br_holidays[datetime.date(2026, 6, 4)] = "Corpus Christi"

    if check_date.weekday() >= 5 or check_date in br_holidays:
        return False
    return True


def pegar_cdi_dia_anterior() -> str:
    """
    Busca os 10 registros mais recentes da taxa CDI via API do Banco Central.

    Returns:
        str: Valor da taxa CDI do registro mais recente ou None se não obtiver dados.
    """
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/10?formato=json"
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.HTTPError:
        print("Dado não encontrado, continuando.")
        return None
    except Exception as exc:
        print("Erro, parando a execução.")
        raise exc
    else:
        if not response.text.strip():
            print("Resposta vazia!")
            return None
        data = json.loads(response.text)
        return data[0]['valor'] if data else None


# ==============================
# Processamento de Cards
# ==============================
def processar_acao(card: dict, props: dict) -> None:
    """
    Processa cards do tipo 'Ação'.
    """
    preco_compra = props.get("Valor Aplicado", {}).get("number")
    quantidade = props.get("Quantidade", {}).get("number")
    try:
        indice = props.get("Indice", {}).get("rich_text", [])[0]['text']['content']
    except (IndexError, KeyError):
        print("Índice não definido para o card.")
        return

    try:
        valor_atual = calculo_acao(indice)
    except Exception as e:
        print(f"Erro ao consultar o ativo {indice}: {e}")
        return

    if preco_compra is None or quantidade is None or valor_atual is None:
        print("Alguma das propriedades numéricas não está definida. Verifique seu database.")
        return

    valor_investido = quantidade * preco_compra
    valor_atual_total = quantidade * valor_atual
    ganho = valor_atual_total - valor_investido
    rendimento_percentual = round((ganho / valor_investido) * 100, 2) / 100

    update_payload = {
        "Rendimento": {"number": rendimento_percentual},
        "Ganho": {"number": ganho},
        "Valor Atual": {"number": valor_atual}
    }
    notion.pages.update(page_id=card["id"], properties=update_payload)


def processar_lca_lci(card: dict, props: dict) -> None:
    """
    Processa cards do tipo 'LCA / LCI'.
    """
    data_hoje = datetime.date.today()
    if not is_business_day(data_hoje):
        return

    valor_aplicado = props.get("Valor Aplicado", {}).get("number")
    try:
        taxa_acumulada_str = props.get("Taxa Acumulada", {}).get("rich_text", [])[0]['text']['content']
    except (IndexError, KeyError):
        print("Taxa Acumulada não definida.")
        return

    # Taxa_aplica e Taxa_anterior são extraídas mas não utilizadas
    # Obter CDI com tratamento de exceção
    while True:
        cdi_valor_str = pegar_cdi_dia_anterior()
        if cdi_valor_str is None:
            print("Não foi possível obter a taxa CDI, tentando novamente...")
            time.sleep(1)
            continue
        try:
            cdi_value = float(cdi_valor_str)
            print(f"CDI: {cdi_value}")
            break
        except Exception as e:
            print("Erro ao converter CDI:", e)
            print("Tentando novamente...")
            time.sleep(1)
    taxa_aplicada = props.get("Taxa de aplicação", {}).get("number")
    # Cálculos para LCA / LCI
    taxa_anual = (Decimal(cdi_value) / Decimal('100')) + Decimal('1')
    taxa_diaria = (taxa_anual ** (Decimal('1') / Decimal('252')) - Decimal('1')).quantize(Decimal('0.00000000'), rounding=ROUND_HALF_UP)
    valor_e = (Decimal('1') + (taxa_diaria * Decimal(taxa_aplicada))).quantize(Decimal('1.000000000000000'), rounding=ROUND_DOWN)

    # Se a taxa acumulada for "1", atualiza apenas os valores e interrompe o processamento do card.
    if taxa_acumulada_str.strip() == "1":
        produto_acumulado = (Decimal('1') * valor_e).quantize(Decimal('1.0000000000000000'), rounding=ROUND_DOWN)
        produto_exibicao = produto_acumulado.quantize(Decimal('0.00000000'), rounding=ROUND_HALF_UP)
        valor_formatado_str = locale.format_string('%.8f', produto_exibicao, grouping=True)
        update_payload = {
            "Rendimento": {"number": 0},
            "Ganho": {"number": 0},
            "Valor Atual": {"number": valor_aplicado},
            "Taxa Acumulada": {
                "rich_text": [
                    {
                    "text": {"content": valor_formatado_str}
                    }
                    ]
                }
            }
        notion.pages.update(page_id=card["id"], properties=update_payload)
        return

    # Caso contrário, realiza os cálculos completos:
    # Converte a string da taxa acumulada para Decimal (removendo formatação)
    produto_acumulado = Decimal(taxa_acumulada_str.replace(".", "").replace(",", "."))
    produto_acumulado *= valor_e
    produto_acumulado = produto_acumulado.quantize(Decimal('1.0000000000000000'), rounding=ROUND_DOWN)
    produto_exibicao = produto_acumulado.quantize(Decimal('0.00000000'), rounding=ROUND_HALF_UP)

    valor_final = (produto_exibicao * Decimal('1000')).quantize(Decimal('0.00000000'), rounding=ROUND_HALF_UP)
    multiplicador = Decimal(valor_aplicado) / Decimal('1000')
    valor_arredondado = valor_final.quantize(Decimal('0.0000'), rounding=ROUND_HALF_UP)
    resultado_final = (multiplicador * valor_arredondado).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
    valor_formatado_str = locale.format_string('%.8f', produto_exibicao, grouping=True)
    ganho = resultado_final - Decimal(valor_aplicado)
    rendimento_percentual = round((ganho / Decimal(valor_aplicado)) * Decimal('100'), 2) / Decimal('100')

    update_payload = {
        "Rendimento": {"number": float(rendimento_percentual)},
        "Ganho": {"number": float(ganho)},
        "Valor Atual": {"number": float(resultado_final)},
        "Taxa Acumulada": {
            "rich_text": [
                {
                "text": {"content": valor_formatado_str}
                }
                ]
            }
        }
    notion.pages.update(page_id=card["id"], properties=update_payload)

def processar_cdb(card: dict, props: dict) -> None:
    """
    Processa cards do tipo 'CDB' e aplica cálculos de rendimento, IR e IOF.
    """
    data_hoje = datetime.date.today()
    # if not is_business_day(data_hoje):
    #     return

    valor_aplicado = props.get("Valor Aplicado", {}).get("number")
    try:
        taxa_acumulada_str = props.get("Taxa Acumulada", {}).get("rich_text", [])[0]['text']['content']
    except (IndexError, KeyError):
        print("Taxa Acumulada não definida.")
        return

    # Obter CDI com tratamento de exceção
    while True:
        cdi_valor_str = pegar_cdi_dia_anterior()
        if cdi_valor_str is None:
            print("Não foi possível obter a taxa CDI, tentando novamente...")
            time.sleep(1)
            continue
        try:
            cdi_value = float(cdi_valor_str)
            print(f"CDI: {cdi_value}")
            break
        except Exception as e:
            print("Erro ao converter CDI:", e)
            print("Tentando novamente...")
            time.sleep(1)

    taxa_aplicada = props.get("Taxa de aplicação", {}).get("number")

    # Cálculos para LCA / LCI
    taxa_anual = (Decimal(cdi_value) / Decimal('100')) + Decimal('1')
    taxa_diaria = (taxa_anual ** (Decimal('1') / Decimal('252')) - Decimal('1')).quantize(Decimal('0.00000000'), rounding=ROUND_HALF_UP)
    valor_e = (Decimal('1') + (taxa_diaria * Decimal(taxa_aplicada))).quantize(Decimal('1.000000000000000'), rounding=ROUND_DOWN)

    # Se a taxa acumulada for "1", atualiza apenas os valores e interrompe o processamento do card.
    if taxa_acumulada_str.strip() == "1":
        produto_acumulado = (Decimal('1') * valor_e).quantize(Decimal('1.0000000000000000'), rounding=ROUND_DOWN)
        produto_exibicao = produto_acumulado.quantize(Decimal('0.00000000'), rounding=ROUND_HALF_UP)
        valor_formatado_str = locale.format_string('%.8f', produto_exibicao, grouping=True)
        update_payload = {
            "Rendimento": {"number": 0},
            "Ganho": {"number": 0},
            "Valor Atual": {"number": valor_aplicado},
            "Taxa Acumulada": {
                "rich_text": [
                    {
                        "text": {"content": valor_formatado_str}
                    }
                ]
            }
        }
        notion.pages.update(page_id=card["id"], properties=update_payload)
        return

    # Caso contrário, realiza os cálculos completos:
    # Converte a string da taxa acumulada para Decimal (removendo formatação)
    produto_acumulado = Decimal(taxa_acumulada_str.replace(".", "").replace(",", "."))
    produto_acumulado *= valor_e
    produto_acumulado = produto_acumulado.quantize(Decimal('1.0000000000000000'), rounding=ROUND_DOWN)
    produto_exibicao = produto_acumulado.quantize(Decimal('0.00000000'), rounding=ROUND_HALF_UP)

    valor_final = (produto_exibicao * Decimal('1000')).quantize(Decimal('0.00000000'), rounding=ROUND_HALF_UP)
    multiplicador = Decimal(valor_aplicado) / Decimal('1000')
    valor_arredondado = valor_final.quantize(Decimal('0.0000'), rounding=ROUND_HALF_UP)
    resultado_final = (multiplicador * valor_arredondado).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)

    # Cálculo do ganho bruto
    ganho = resultado_final - Decimal(valor_aplicado)

    # Recupera a data de aplicação (supondo o formato "YYYY-MM-DD")
    data_aplicacao = props.get('Compra', {}).get('date', {}).get("start")
    if not data_aplicacao:
        print("Data de aplicação não definida.")
        return
    try:
        data_aplicacao_dt = datetime.datetime.strptime(data_aplicacao, "%Y-%m-%d")
    except Exception as e:
        print("Erro ao converter data de aplicação:", e)
        return

    # Calcula o número de dias entre a data de aplicação e hoje
    dias_investido = (data_hoje - data_aplicacao_dt.date()).days

    # --- CÁLCULO DOS IMPOSTOS ---

    # Imposto de Renda (IR) - tributação regressiva sobre o rendimento
    if dias_investido <= 180:
        taxa_ir = Decimal('0.225')
    elif dias_investido <= 360:
        taxa_ir = Decimal('0.20')
    elif dias_investido <= 720:
        taxa_ir = Decimal('0.175')
    else:
        taxa_ir = Decimal('0.15')
    print(ganho)
    print(taxa_ir)
    ir = ganho * taxa_ir

    # IOF (Imposto sobre Operações Financeiras)
    # Cobrado somente se o resgate ocorrer em até 30 dias da aplicação
    if dias_investido < 30:
        # Considerando uma redução linear: 96% no 1º dia, 0% no 30º dia
        iof_rate = Decimal('0.96') * (Decimal(30 - dias_investido) / Decimal('30'))
        iof = ganho * iof_rate
    else:
        iof = Decimal('0')

    # Ganho líquido após descontos
    ganho_liquido = ganho - ir - iof
    print(resultado_final)
    print(ir)
    print(iof)
    valor_resgate_liquido = resultado_final - ir - iof
    print(valor_resgate_liquido)

    # Cálculo do rendimento percentual líquido
    rendimento_percentual = (ganho_liquido / Decimal(valor_aplicado)).quantize(Decimal('0.0000'), rounding=ROUND_HALF_UP)

    # Formatação para exibição
    valor_formatado_str = locale.format_string('%.8f', produto_exibicao, grouping=True)
    update_payload = {
        "Rendimento": {"number": float(rendimento_percentual)},
        "Ganho": {"number": float(ganho_liquido)},
        "Valor Atual": {"number": float(valor_resgate_liquido)},
        "Taxa Acumulada": {
            "rich_text": [
                {
                    "text": {"content": valor_formatado_str}
                }
            ]
        }
    }
    notion.pages.update(page_id=card["id"], properties=update_payload)


def processar_cards() -> None:
    """
    Consulta o database do Notion e processa cada card conforme seu tipo.
    """
    response = notion.databases.query(database_id=DATABASE_ID)
    pages = response.get("results", [])

    if not pages:
        print("Nenhum card encontrado no database.")
        return

    for card in pages:
        props = card["properties"]
        tipo = props.get("Tipo", {}).get("select", {}).get("name")
        if tipo == "Ação":
            processar_acao(card, props)
        elif tipo == "LCA / LCI":
            processar_lca_lci(card, props)
        elif tipo == "CDB":
            processar_cdb(card,props)


# ==============================
# Execução Principal
# ==============================
if __name__ == "__main__":
    processar_cards()

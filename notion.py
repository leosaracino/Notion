"""
Automacao Notion - Portfolio de Investimentos.

Le cards do database Notion, calcula rendimento conforme o tipo do ativo
e escreve de volta no Notion.

Tipos suportados:
  - Acao (BR e US)  -> brapi.dev / yfinance
  - LCA / LCI       -> CDI da serie 4389 do BCB
  - CDB             -> CDI + IR regressivo + IOF tabelado
  - ESPP            -> IBM Employee Stock Purchase Plan (15% desconto)
"""

import datetime
import json
import locale
import logging
import os
import time
from decimal import Decimal, getcontext, ROUND_HALF_UP, ROUND_DOWN
from functools import lru_cache

import requests
from anbima_calendar import is_business_day as anbima_is_business_day
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
BRAPI_TOKEN = os.getenv("BRAPI_TOKEN")

if not all([NOTION_TOKEN, DATABASE_ID, BRAPI_TOKEN]):
    raise RuntimeError("Variaveis .env faltando: NOTION_TOKEN, DATABASE_ID, BRAPI_TOKEN")

getcontext().prec = 30
try:
    locale.setlocale(locale.LC_ALL, "pt_BR.UTF-8")
except locale.Error:
    locale.setlocale(locale.LC_ALL, "Portuguese_Brazil.1252")

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

notion = Client(auth=NOTION_TOKEN)

# Tabela oficial de IOF para resgates ate 30 dias (% sobre rendimento)
IOF_TABLE = [
    96, 93, 90, 86, 83, 80, 76, 73, 70, 66,
    63, 60, 56, 53, 50, 46, 43, 40, 36, 33,
    30, 26, 23, 20, 16, 13, 10, 6, 3, 0,
]

# IBM ESPP: 15% desconto a partir de 01/04/2022
IBM_ESPP_DISCOUNT = Decimal("0.15")


def is_business_day(check_date: datetime.date) -> bool:
    """Calendario ANBIMA - cobre 1969-2068, incluindo Carnaval e Corpus Christi."""
    return anbima_is_business_day(check_date)


def cotacao_br(ticker: str) -> float:
    """Cotacao via brapi.dev (acoes BR: PETR4, VALE3, etc)."""
    url = f"https://brapi.dev/api/quote/{ticker}?token={BRAPI_TOKEN}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    try:
        return float(data["results"][0]["regularMarketPrice"])
    except (KeyError, IndexError) as exc:
        raise ValueError(f"Brapi: dados invalidos para {ticker}") from exc


def cotacao_us(ticker: str) -> float:
    """Cotacao via yfinance (acoes US: IBM, AAPL, etc)."""
    import yfinance as yf
    info = yf.Ticker(ticker).fast_info
    price = info.get("last_price") or info.get("regular_market_price")
    if price is None:
        raise ValueError(f"yfinance: sem cotacao para {ticker}")
    return float(price)


def cotacao(ticker: str, mercado: str = "BR") -> float:
    """Dispatcher para o mercado certo."""
    return cotacao_us(ticker) if mercado.upper() == "US" else cotacao_br(ticker)


@lru_cache(maxsize=1)
def cdi_anual_pct() -> float:
    """CDI anual % a.a. da serie 4389 (BCB). Cacheado por execucao."""
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/10?formato=json"
    for tentativa in range(5):
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = json.loads(r.text)
            if data:
                cdi = float(data[0]["valor"])
                log.info("CDI (%s): %.2f%% a.a.", data[0]["data"], cdi)
                return cdi
        except Exception as exc:
            log.warning("Tentativa %s falhou: %s", tentativa + 1, exc)
            time.sleep(1)
    raise RuntimeError("Nao foi possivel obter CDI apos 5 tentativas")


def fator_diario_cdi(taxa_aplicada_pct: float) -> Decimal:
    """
    Fator multiplicativo de UM dia util sobre o CDI corrente.

    taxa_aplicada_pct: % do CDI contratado (ex: 100 = 100% do CDI, 110 = 110%)
    """
    cdi = Decimal(str(cdi_anual_pct()))
    return _fator_de_cdi(cdi, taxa_aplicada_pct)


def _fator_de_cdi(cdi_anual: Decimal, taxa_aplicada_pct: float) -> Decimal:
    taxa_anual = (cdi_anual / Decimal("100")) + Decimal("1")
    taxa_diaria = (taxa_anual ** (Decimal("1") / Decimal("252")) - Decimal("1")).quantize(
        Decimal("0.00000000"), rounding=ROUND_HALF_UP
    )
    return (Decimal("1") + (taxa_diaria * Decimal(str(taxa_aplicada_pct)))).quantize(
        Decimal("1.000000000000000"), rounding=ROUND_DOWN
    )


@lru_cache(maxsize=8)
def historico_cdi(data_inicio: datetime.date, data_fim: datetime.date) -> list[tuple[datetime.date, Decimal]]:
    """Serie 4389 entre duas datas. Retorna lista [(data, cdi_anual_pct)]."""
    di = data_inicio.strftime("%d/%m/%Y")
    df = data_fim.strftime("%d/%m/%Y")
    url = (
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados"
        f"?formato=json&dataInicial={di}&dataFinal={df}"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    out = []
    for item in r.json():
        d = datetime.datetime.strptime(item["data"], "%d/%m/%Y").date()
        out.append((d, Decimal(item["valor"])))
    return out


def calcular_retroativo_cdi(
    valor_aplicado: float,
    data_compra: datetime.date,
    taxa_aplicada_pct: float,
    ate: datetime.date | None = None,
) -> tuple[Decimal, Decimal]:
    """
    Calcula valor bruto acumulado de um titulo CDI da data de compra ate hoje.

    Retorna (produto_acumulado, valor_bruto_atual).
    """
    ate = ate or datetime.date.today()
    historia = historico_cdi(data_compra, ate)

    produto = Decimal("1")
    for data_cdi, cdi in historia:
        if not is_business_day(data_cdi):
            continue
        produto *= _fator_de_cdi(cdi, taxa_aplicada_pct)

    produto = produto.quantize(Decimal("1.0000000000000000"), rounding=ROUND_DOWN)
    valor_bruto = (Decimal(str(valor_aplicado)) * produto).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return produto, valor_bruto


def calcular_ir_iof(ganho_bruto: Decimal, dias_investido: int) -> tuple[Decimal, Decimal]:
    """IR regressivo e IOF tabelado para CDB. Retorna (ir, iof)."""
    if dias_investido <= 180:
        taxa_ir = Decimal("0.225")
    elif dias_investido <= 360:
        taxa_ir = Decimal("0.20")
    elif dias_investido <= 720:
        taxa_ir = Decimal("0.175")
    else:
        taxa_ir = Decimal("0.15")
    ir = ganho_bruto * taxa_ir

    if 1 <= dias_investido <= 30:
        iof_pct = Decimal(IOF_TABLE[dias_investido - 1]) / Decimal("100")
        iof = ganho_bruto * iof_pct
    else:
        iof = Decimal("0")
    return ir, iof


def formatar_taxa(produto: Decimal) -> str:
    return locale.format_string("%.8f", produto, grouping=True)


# Campos de moeda - usuario pode ter "Valor Aplicado", "Valor Aplicado R$" e/ou "Valor Aplicado  $"
CAMPO_VALOR_BR = ("Valor Aplicado R$", "Valor Aplicado")
CAMPO_VALOR_US = ("Valor Aplicado  $", "Valor Aplicado $", "Valor Aplicado")


def _ler_valor_aplicado(props: dict, mercado: str = "BR") -> tuple[float | None, str]:
    """Le Valor Aplicado tentando variantes de nome conforme moeda. Retorna (valor, campo_usado)."""
    candidatos = CAMPO_VALOR_US if mercado.upper() == "US" else CAMPO_VALOR_BR
    for nome in candidatos:
        prop = props.get(nome)
        if prop and prop.get("number") is not None:
            return prop["number"], nome
    return None, ""


def processar_acao(card: dict, props: dict) -> None:
    mercado = (props.get("Mercado", {}).get("select") or {}).get("name", "BR")
    preco_compra, _ = _ler_valor_aplicado(props, mercado)
    quantidade = props.get("Quantidade", {}).get("number")
    try:
        ticker = props["Indice"]["rich_text"][0]["text"]["content"]
    except (KeyError, IndexError):
        log.warning("Indice nao definido")
        return

    try:
        valor_atual = cotacao(ticker, mercado)
    except Exception as exc:
        log.error("Erro cotacao %s (%s): %s", ticker, mercado, exc)
        return

    if preco_compra is None or quantidade is None:
        log.warning("Propriedades faltando em %s", ticker)
        return

    investido = quantidade * preco_compra
    atual_total = quantidade * valor_atual
    ganho = atual_total - investido
    rendimento = round((ganho / investido) * 100, 2) / 100

    notion.pages.update(page_id=card["id"], properties={
        "Rendimento": {"number": rendimento},
        "Ganho": {"number": ganho},
        "Valor Atual": {"number": valor_atual},
    })
    log.info("Acao %s: %.2f -> ganho R$ %.2f (%.2f%%)", ticker, valor_atual, ganho, rendimento * 100)


def _processar_renda_fixa(card: dict, props: dict, com_impostos: bool) -> None:
    """Logica comum LCA/LCI/CDB. com_impostos=True para CDB."""
    if not is_business_day(datetime.date.today()):
        log.info("Hoje nao e dia util, pulando renda fixa")
        return

    valor_aplicado, _ = _ler_valor_aplicado(props, "BR")  # renda fixa BR sempre
    if valor_aplicado is None:
        log.warning("Valor Aplicado faltando")
        return

    try:
        taxa_acumulada_str = props["Taxa Acumulada"]["rich_text"][0]["text"]["content"]
    except (KeyError, IndexError):
        log.warning("Taxa Acumulada nao definida")
        return

    taxa_aplicada = props.get("Taxa de aplicação", {}).get("number")
    if taxa_aplicada is None:
        log.warning("Taxa de aplicacao nao definida")
        return

    valor_e = fator_diario_cdi(taxa_aplicada)

    # Caso especial: taxa acumulada == "1" significa primeira execucao
    if taxa_acumulada_str.strip() == "1":
        produto_acumulado = (Decimal("1") * valor_e).quantize(
            Decimal("1.0000000000000000"), rounding=ROUND_DOWN
        )
        produto_exibicao = produto_acumulado.quantize(
            Decimal("0.00000000"), rounding=ROUND_HALF_UP
        )
        notion.pages.update(page_id=card["id"], properties={
            "Rendimento": {"number": 0},
            "Ganho": {"number": 0},
            "Valor Atual": {"number": valor_aplicado},
            "Taxa Acumulada": {"rich_text": [{"text": {"content": formatar_taxa(produto_exibicao)}}]},
        })
        return

    produto_acumulado = Decimal(taxa_acumulada_str.replace(".", "").replace(",", "."))
    produto_acumulado = (produto_acumulado * valor_e).quantize(
        Decimal("1.0000000000000000"), rounding=ROUND_DOWN
    )
    produto_exibicao = produto_acumulado.quantize(Decimal("0.00000000"), rounding=ROUND_HALF_UP)

    valor_final = (produto_exibicao * Decimal("1000")).quantize(
        Decimal("0.00000000"), rounding=ROUND_HALF_UP
    )
    multiplicador = Decimal(str(valor_aplicado)) / Decimal("1000")
    valor_arredondado = valor_final.quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)
    resultado_bruto = (multiplicador * valor_arredondado).quantize(
        Decimal("0.00"), rounding=ROUND_HALF_UP
    )
    ganho_bruto = resultado_bruto - Decimal(str(valor_aplicado))

    if not com_impostos:
        # LCA/LCI: isento de IR e IOF
        rendimento = round((ganho_bruto / Decimal(str(valor_aplicado))) * Decimal("100"), 2) / Decimal("100")
        notion.pages.update(page_id=card["id"], properties={
            "Rendimento": {"number": float(rendimento)},
            "Ganho": {"number": float(ganho_bruto)},
            "Valor Atual": {"number": float(resultado_bruto)},
            "Taxa Acumulada": {"rich_text": [{"text": {"content": formatar_taxa(produto_exibicao)}}]},
        })
        return

    # CDB - calcular IR + IOF
    data_aplicacao_str = props.get("Compra", {}).get("date", {}).get("start")
    if not data_aplicacao_str:
        log.warning("Data de Compra faltando no CDB")
        return
    try:
        data_aplicacao = datetime.datetime.strptime(data_aplicacao_str, "%Y-%m-%d").date()
    except ValueError:
        log.warning("Data de Compra invalida: %s", data_aplicacao_str)
        return

    dias_investido = (datetime.date.today() - data_aplicacao).days
    ir, iof = calcular_ir_iof(ganho_bruto, dias_investido)
    ganho_liquido = ganho_bruto - ir - iof
    valor_resgate_liquido = resultado_bruto - ir - iof
    rendimento = (ganho_liquido / Decimal(str(valor_aplicado))).quantize(
        Decimal("0.0000"), rounding=ROUND_HALF_UP
    )
    log.info("CDB %d dias: bruto %.2f, IR %.2f, IOF %.2f, liq %.2f",
             dias_investido, ganho_bruto, ir, iof, ganho_liquido)

    notion.pages.update(page_id=card["id"], properties={
        "Rendimento": {"number": float(rendimento)},
        "Ganho": {"number": float(ganho_liquido)},
        "Valor Atual": {"number": float(valor_resgate_liquido)},
        "Taxa Acumulada": {"rich_text": [{"text": {"content": formatar_taxa(produto_exibicao)}}]},
    })


def processar_lca_lci(card: dict, props: dict) -> None:
    _processar_renda_fixa(card, props, com_impostos=False)


def processar_cdb(card: dict, props: dict) -> None:
    _processar_renda_fixa(card, props, com_impostos=True)


def processar_espp(card: dict, props: dict) -> None:
    """
    Plano IBM ESPP. Atualiza valor de mercado da posicao.

    Campos esperados no Notion:
      - Indice (rich_text): ticker (ex: IBM)
      - Quantidade (number): acoes acumuladas
      - Valor Aplicado (number): preco medio efetivo pago (ja com 15% desconto)

    A acumulacao mensal (10% do salario -> caixa) e a compra semestral
    (Jan 1 / Jul 1) sao logicas adicionais que precisam de campos novos
    (Salario, Contribuicao Acumulada, Proxima Compra). Ver doc no final.
    """
    try:
        ticker = props["Indice"]["rich_text"][0]["text"]["content"]
    except (KeyError, IndexError):
        ticker = "IBM"

    quantidade = props.get("Quantidade", {}).get("number") or 0
    preco_medio, _ = _ler_valor_aplicado(props, "US")
    preco_medio = preco_medio or 0

    try:
        preco_atual = cotacao_us(ticker)
    except Exception as exc:
        log.error("ESPP %s: %s", ticker, exc)
        return

    valor_mercado = quantidade * preco_atual
    investido = quantidade * preco_medio
    ganho = valor_mercado - investido
    rendimento = (ganho / investido) if investido else 0

    notion.pages.update(page_id=card["id"], properties={
        "Rendimento": {"number": float(rendimento)},
        "Ganho": {"number": float(ganho)},
        "Valor Atual": {"number": float(preco_atual)},
    })
    log.info("ESPP %s: %d acoes x USD %.2f = USD %.2f (ganho %.2f)",
             ticker, quantidade, preco_atual, valor_mercado, ganho)


PROCESSADORES = {
    "Ação": processar_acao,
    "LCA / LCI": processar_lca_lci,
    "CDB": processar_cdb,
    "ESPP": processar_espp,
}


def processar_cards() -> None:
    pages = notion.databases.query(database_id=DATABASE_ID).get("results", [])
    if not pages:
        log.warning("Nenhum card encontrado no database")
        return

    log.info("%d cards encontrados", len(pages))
    for card in pages:
        props = card["properties"]
        tipo = (props.get("Tipo", {}).get("select") or {}).get("name")
        if not tipo:
            continue
        processador = PROCESSADORES.get(tipo)
        if processador:
            try:
                processador(card, props)
            except Exception as exc:
                log.exception("Erro ao processar card tipo=%s: %s", tipo, exc)
        else:
            log.debug("Tipo nao suportado: %s", tipo)


if __name__ == "__main__":
    processar_cards()

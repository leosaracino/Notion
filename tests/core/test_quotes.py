"""Parsing das cotacoes externas e a deduplicacao de tickers (sem rede)."""

import pytest

from portfolio.core import quotes

CSV_STOOQ = (
    "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
    "IBM.US,2026-09-01,22:00:05,230.10,232.40,229.80,231.51,3210000\n"
    "AAPL.US,2026-09-01,22:00:05,180.00,182.00,179.50,181.25,9100000\n"
)


def test_parse_yahoo():
    assert quotes.parse_yahoo({"chart": {"result": [{"meta": {"regularMarketPrice": 231.51}}]}}) == 231.51


def test_parse_yahoo_recusa_preco_zerado():
    with pytest.raises(ValueError):
        quotes.parse_yahoo({"chart": {"result": [{"meta": {"regularMarketPrice": 0}}]}})


def test_parse_stooq_devolve_um_preco_por_ticker():
    assert quotes.parse_stooq(CSV_STOOQ) == {"IBM": 231.51, "AAPL": 181.25}


def test_parse_stooq_ignora_ticker_sem_cotacao():
    csv = "Symbol,Date,Time,Open,High,Low,Close,Volume\nXPTO.US,N/D,N/D,N/D,N/D,N/D,N/D,N/D\n"

    assert quotes.parse_stooq(csv) == {}


def test_parse_awesomeapi():
    assert quotes.parse_awesome({"USDBRL": {"bid": "5.1579", "ask": "5.1585"}}) == 5.1579


def test_parse_ptax():
    assert quotes.parse_ptax([{"data": "01/09/2026", "valor": "5.1579"}]) == 5.1579


def test_busca_cada_ticker_uma_vez_so(monkeypatch):
    chamadas = []

    def falso_yahoo(ticker):
        chamadas.append(ticker)
        return 231.51

    monkeypatch.setattr(quotes, "_preco_yahoo", falso_yahoo)

    # Mesmo ticker pedido por varias plataformas, em caixas diferentes.
    assert quotes.precos(["IBM", "ibm", " IBM "]) == {"IBM": 231.51}
    assert chamadas == ["IBM"]


def test_cai_para_o_stooq_em_lote_unico(monkeypatch):
    lotes = []

    def yahoo_quebrado(ticker):
        raise RuntimeError("429")

    def falso_stooq(tickers):
        lotes.append(list(tickers))
        return {"IBM": 231.51, "AAPL": 181.25}

    monkeypatch.setattr(quotes, "_preco_yahoo", yahoo_quebrado)
    monkeypatch.setattr(quotes, "_precos_stooq", falso_stooq)

    assert quotes.precos(["IBM", "AAPL"]) == {"IBM": 231.51, "AAPL": 181.25}
    assert lotes == [["AAPL", "IBM"]]  # uma chamada so, com os dois


def test_erro_quando_ticker_nao_tem_cotacao(monkeypatch):
    monkeypatch.setattr(quotes, "_preco_yahoo", lambda t: (_ for _ in ()).throw(RuntimeError("nao existe")))
    monkeypatch.setattr(quotes, "_precos_stooq", lambda t: {})

    with pytest.raises(RuntimeError, match="XPTO"):
        quotes.precos(["XPTO"])


def test_sem_tickers_nao_chama_ninguem():
    assert quotes.precos([]) == {}

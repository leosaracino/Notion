"""Cotacoes externas: preco de acoes (em lote) e cambio USD/BRL.

Cada ticker e buscado uma unica vez por execucao, mesmo que varias plataformas
precisem dele (o ESPP e a carteira de acoes podem ter a mesma empresa).

Fontes tem fallback porque API publica gratuita cai e limita sem aviso:
  - acoes: Yahoo por ticker; o que falhar vai num lote unico para o Stooq
  - cambio: AwesomeAPI, com PTAX/BCB de reserva
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Iterable

import requests

log = logging.getLogger(__name__)

TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; notion-portfolio/1.0)"}


# --------------------------------------------------------------------- acoes


def precos(tickers: Iterable[str]) -> dict[str, float]:
    """Preco em USD de cada ticker. Levanta erro se algum nao for encontrado."""
    pendentes = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    if not pendentes:
        return {}

    encontrados: dict[str, float] = {}
    for ticker in pendentes:
        try:
            encontrados[ticker] = _preco_yahoo(ticker)
        except Exception as exc:
            log.warning("Yahoo falhou para %s: %s", ticker, exc)

    faltando = [t for t in pendentes if t not in encontrados]
    if faltando:
        log.info("Buscando %s no Stooq (lote unico).", ", ".join(faltando))
        try:
            encontrados.update(_precos_stooq(faltando))
        except Exception as exc:
            log.warning("Stooq falhou: %s", exc)

    faltando = [t for t in pendentes if t not in encontrados]
    if faltando:
        raise RuntimeError(f"Sem cotacao para: {', '.join(faltando)}")

    for ticker, preco in encontrados.items():
        log.info("%s = US$ %.2f", ticker, preco)
    return encontrados


def _preco_yahoo(ticker: str) -> float:
    resp = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
        params={"range": "1d", "interval": "1d"},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return parse_yahoo(resp.json())


def _precos_stooq(tickers: list[str]) -> dict[str, float]:
    resp = requests.get(
        "https://stooq.com/q/l/",
        params={
            "s": "+".join(f"{t.lower()}.us" for t in tickers),
            "f": "sd2t2ohlcv",
            "h": "",
            "e": "csv",
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return parse_stooq(resp.text)


def parse_yahoo(payload: dict[str, Any]) -> float:
    meta = payload["chart"]["result"][0]["meta"]
    preco = float(meta["regularMarketPrice"])
    if preco <= 0:
        raise ValueError(f"preco invalido: {preco}")
    return preco


def parse_stooq(texto_csv: str) -> dict[str, float]:
    """O Stooq devolve uma linha por ticker; ausentes vem com 'N/D'."""
    achados: dict[str, float] = {}
    for linha in csv.DictReader(io.StringIO(texto_csv)):
        simbolo = (linha.get("Symbol") or "").upper().removesuffix(".US")
        try:
            preco = float(linha["Close"])
        except (TypeError, ValueError):
            continue
        if simbolo and preco > 0:
            achados[simbolo] = preco
    return achados


# -------------------------------------------------------------------- cambio


def cambio_usd_brl() -> float:
    """Quantos reais valem 1 dolar agora."""
    erros = []
    for nome, fonte in (("awesomeapi", _cambio_awesome), ("bcb_ptax", _cambio_ptax)):
        try:
            valor = fonte()
        except Exception as exc:
            log.warning("Fonte %s falhou (cambio): %s", nome, exc)
            erros.append(f"{nome}: {exc}")
            continue
        if valor > 0:
            log.info("Cambio USD/BRL = %.4f (via %s)", valor, nome)
            return valor
        erros.append(f"{nome}: retornou {valor}")

    raise RuntimeError(f"Nenhuma fonte respondeu para o cambio. Erros: {'; '.join(erros)}")


def _cambio_awesome() -> float:
    resp = requests.get(
        "https://economia.awesomeapi.com.br/json/last/USD-BRL",
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return parse_awesome(resp.json())


def _cambio_ptax() -> float:
    # Serie 1 do SGS = dolar comercial (venda), fechamento do dia util anterior.
    resp = requests.get(
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados/ultimos/1",
        params={"formato": "json"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return parse_ptax(resp.json())


def parse_awesome(payload: dict[str, Any]) -> float:
    return float(payload["USDBRL"]["bid"])


def parse_ptax(payload: list[dict[str, Any]]) -> float:
    return float(payload[-1]["valor"])


# Atalho para quem precisa de um ticker so.
def preco_acao(ticker: str) -> float:
    return precos([ticker])[ticker.upper()]

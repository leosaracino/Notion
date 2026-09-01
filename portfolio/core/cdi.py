"""Serie diaria do CDI (BCB/SGS serie 12) e correcao de valores pelo CDI acumulado.

Buscada uma unica vez por execucao, a partir do investimento mais antigo de
toda a base — ESPP, acoes e renda fixa usam a mesma serie.

A regra de correcao e a mesma que a planilha usava:

    valor_corrigido = valor * PRODUCT(1 + cdi_do_dia/100) para todo dia > data_da_compra

O dia da compra nao rende; os dias uteis seguintes rendem. A serie 12 ja vem em
% ao dia, entao nao ha conversao de taxa anual envolvida.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Sequence

import requests

log = logging.getLogger(__name__)

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
SERIE_CDI_DIARIO = 12
TIMEOUT = 30
TENTATIVAS = 4

# O SGS recusa intervalos longos demais em series diarias; buscamos em blocos.
ANOS_POR_REQUISICAO = 8

SerieCDI = list[tuple[date, float]]


def buscar_serie(desde: date, ate: date | None = None, serie: int = SERIE_CDI_DIARIO) -> SerieCDI:
    """Baixa a serie diaria do CDI, em blocos quando o intervalo e longo."""
    fim = ate or date.today()
    if desde > fim:
        return []

    completa: SerieCDI = []
    inicio_bloco = desde
    while inicio_bloco <= fim:
        fim_bloco = min(_somar_anos(inicio_bloco, ANOS_POR_REQUISICAO), fim)
        completa.extend(_buscar_bloco(inicio_bloco, fim_bloco, serie))
        inicio_bloco = fim_bloco + timedelta(days=1)

    completa.sort(key=lambda par: par[0])
    if completa:
        log.info("CDI: %d dias (%s a %s).", len(completa), completa[0][0], completa[-1][0])
    else:
        log.warning("CDI: nenhum dia retornado para o intervalo %s a %s.", desde, fim)
    return completa


def _somar_anos(dia: date, anos: int) -> date:
    try:
        return dia.replace(year=dia.year + anos)
    except ValueError:  # 29/02
        return dia.replace(year=dia.year + anos, day=28)


def _buscar_bloco(inicio: date, fim: date, serie: int) -> SerieCDI:
    params = {
        "formato": "json",
        "dataInicial": inicio.strftime("%d/%m/%Y"),
        "dataFinal": fim.strftime("%d/%m/%Y"),
    }

    ultimo_erro: Exception | None = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resp = requests.get(URL.format(serie=serie), params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return parse_serie(resp.json())
        except Exception as exc:  # o BCB cai com alguma frequencia
            ultimo_erro = exc
            log.warning("BCB tentativa %d/%d falhou: %s", tentativa, TENTATIVAS, exc)
            if tentativa < TENTATIVAS:
                time.sleep(2**tentativa)

    raise RuntimeError(f"Nao foi possivel baixar a serie {serie} do BCB: {ultimo_erro}")


def parse_serie(dados: Iterable[dict[str, Any]]) -> SerieCDI:
    serie = [
        (datetime.strptime(item["data"], "%d/%m/%Y").date(), float(item["valor"]))
        for item in dados
    ]
    serie.sort(key=lambda par: par[0])
    return serie


def fator_acumulado(serie: Sequence[tuple[date, float]], desde: date, ate: date | None = None) -> float:
    """Produto de (1 + taxa/100) dos dias estritamente depois de `desde`."""
    fator = 1.0
    for dia, taxa in serie:
        if dia <= desde:
            continue
        if ate is not None and dia > ate:
            break
        fator *= 1 + taxa / 100
    return fator


def corrigir(valor: float, serie: Sequence[tuple[date, float]], desde: date, casas: int = 2) -> float:
    """Valor corrigido pelo CDI acumulado desde a data informada."""
    return round(valor * fator_acumulado(serie, desde), casas)

"""A esteira: coleta uma vez o que e comum e roda as plataformas em sequencia.

    1. cada plataforma carrega suas linhas do Notion e declara seus requisitos
       (investimento mais antigo, tickers, se usa CDI e cambio);
    2. a esteira junta os requisitos de todas e faz as buscas externas uma unica
       vez — CDI desde o investimento mais antigo de toda a base, um preco por
       ticker, um cambio;
    3. cada plataforma recebe esse contexto e atualiza o que e dela.

Plataforma nova (acoes, renda fixa) e so implementar `Plataforma` e incluir na
lista passada para `executar`.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

from . import cdi as cdi_mod
from . import quotes

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Requisitos:
    """O que uma plataforma precisa que a esteira busque para ela."""

    data_mais_antiga: date | None = None
    tickers: frozenset[str] = frozenset()
    precisa_cdi: bool = False
    precisa_cambio: bool = False


@dataclass(frozen=True)
class Contexto:
    """Dados externos ja buscados, compartilhados por todas as plataformas."""

    hoje: date
    precos: dict[str, float] = field(default_factory=dict)
    cambio_usd_brl: float | None = None
    cdi: cdi_mod.SerieCDI = field(default_factory=list)

    def preco(self, ticker: str) -> float:
        try:
            return self.precos[ticker.upper()]
        except KeyError:
            raise RuntimeError(f"Preco de {ticker} nao foi buscado nesta execucao.") from None

    def cambio(self) -> float:
        if self.cambio_usd_brl is None:
            raise RuntimeError("Cambio nao foi buscado nesta execucao.")
        return self.cambio_usd_brl


@dataclass(frozen=True)
class Resultado:
    plataforma: str
    linhas: int
    atualizadas: int


class Plataforma(ABC):
    """Contrato que ESPP, acoes e renda fixa implementam."""

    nome: str

    @abstractmethod
    def carregar(self) -> int:
        """Le as linhas do Notion e devolve quantas encontrou."""

    @abstractmethod
    def requisitos(self) -> Requisitos:
        """Declara o que precisa; so e chamado depois de `carregar`."""

    @abstractmethod
    def atualizar(self, contexto: Contexto, dry_run: bool = False) -> Resultado:
        """Calcula e grava o que for dela."""


def juntar(requisitos: list[Requisitos]) -> Requisitos:
    """Agrega os requisitos de todas as plataformas num so."""
    datas = [r.data_mais_antiga for r in requisitos if r.data_mais_antiga]
    tickers: set[str] = set()
    for req in requisitos:
        tickers |= {t.upper() for t in req.tickers}

    return Requisitos(
        data_mais_antiga=min(datas) if datas else None,
        tickers=frozenset(tickers),
        precisa_cdi=any(r.precisa_cdi for r in requisitos),
        precisa_cambio=any(r.precisa_cambio for r in requisitos),
    )


def coletar(req: Requisitos, hoje: date | None = None) -> Contexto:
    """Faz as buscas externas uma unica vez, conforme os requisitos agregados."""
    hoje = hoje or date.today()

    precos_por_ticker = quotes.precos(req.tickers) if req.tickers else {}
    cambio = quotes.cambio_usd_brl() if req.precisa_cambio else None

    serie: cdi_mod.SerieCDI = []
    if req.precisa_cdi:
        if req.data_mais_antiga:
            log.info("Investimento mais antigo da base: %s", req.data_mais_antiga)
            serie = cdi_mod.buscar_serie(desde=req.data_mais_antiga, ate=hoje)
        else:
            log.warning("Nenhuma data de investimento encontrada - CDI nao sera buscado.")

    return Contexto(hoje=hoje, precos=precos_por_ticker, cambio_usd_brl=cambio, cdi=serie)


def executar(plataformas: list[Plataforma], dry_run: bool = False) -> list[Resultado]:
    ativas: list[Plataforma] = []
    for plataforma in plataformas:
        linhas = plataforma.carregar()
        log.info("%s: %d linha(s) carregada(s).", plataforma.nome, linhas)
        if linhas:
            ativas.append(plataforma)
        else:
            log.warning("%s: sem linhas, sera ignorada.", plataforma.nome)

    if not ativas:
        log.warning("Nenhuma plataforma com dados - nada a fazer.")
        return []

    contexto = coletar(juntar([p.requisitos() for p in ativas]))

    resultados = []
    for plataforma in ativas:
        resultados.append(plataforma.atualizar(contexto, dry_run=dry_run))
    return resultados

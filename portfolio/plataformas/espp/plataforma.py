"""Plataforma ESPP: o que so o ESPP sabe.

Quais colunas existem na database, quais a automacao escreve, como corrigir o
valor descontado pelo CDI e como ligar os lancamentos a pagina de resumo.
Preco da acao, cambio e serie do CDI chegam prontos pela esteira.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from ...core import cdi as cdi_mod
from ...core import notion
from ...core.pipeline import Contexto, Plataforma, Requisitos, Resultado
from . import calculos

log = logging.getLogger(__name__)

TICKER = "IBM"
TOLERANCIA = 1e-9

# Nomes exatos das propriedades no Notion (acentos incluidos).
PROP_NOME = "Nome"
PROP_DATA = "Data da compra"
PROP_TIPO = "Tipo"
PROP_DESCONTADO = "Valor descontado (BRL)"
PROP_CORRIGIDO = "Valor descontado corrigido (BRL)"
PROP_TAXA = "Taxa (USD)"
PROP_DOLAR = "Dólar comprado (USD)"
PROP_PRECO_COMPRA = "Preço de compra c/ desconto (USD)"
PROP_PRECO_HOJE = "Preço IBM hoje (USD)"
PROP_CAMBIO_HOJE = "Câmbio hoje (USD/BRL)"
PROP_ATUALIZADO = "Última atualização"

# Propriedade da pagina ESPP que alimenta os rollups do resumo.
PROP_LANCAMENTOS = "Lançamentos"


@dataclass(frozen=True)
class Linha:
    """Uma compra via folha ou um reinvestimento de dividendo."""

    page_id: str
    nome: str
    data: date | None
    tipo: str | None
    valor_descontado: float | None
    valor_corrigido: float | None
    taxa: float | None
    dolar_comprado: float | None
    preco_compra_desc: float | None
    preco_hoje: float | None
    cambio_hoje: float | None


def ler_linha(pagina: dict[str, Any]) -> Linha:
    props = pagina.get("properties", {})
    return Linha(
        page_id=pagina["id"],
        nome=notion.titulo(props, PROP_NOME),
        data=notion.data(props, PROP_DATA),
        tipo=notion.selecao(props, PROP_TIPO),
        valor_descontado=notion.numero(props, PROP_DESCONTADO),
        valor_corrigido=notion.numero(props, PROP_CORRIGIDO),
        taxa=notion.numero(props, PROP_TAXA),
        dolar_comprado=notion.numero(props, PROP_DOLAR),
        preco_compra_desc=notion.numero(props, PROP_PRECO_COMPRA),
        preco_hoje=notion.numero(props, PROP_PRECO_HOJE),
        cambio_hoje=notion.numero(props, PROP_CAMBIO_HOJE),
    )


@dataclass
class Plano:
    """O que a automacao pretende gravar numa linha."""

    linha: Linha
    corrigido: float
    precisa_gravar: bool


def montar_plano(linha: Linha, serie: cdi_mod.SerieCDI, preco: float, cambio: float) -> Plano | None:
    if linha.data is None:
        log.warning("Linha '%s' esta sem 'Data da compra' - ignorada.", linha.nome or linha.page_id)
        return None

    descontado = linha.valor_descontado or 0.0
    corrigido = cdi_mod.corrigir(descontado, serie, linha.data) if descontado else 0.0

    precisa = (
        not _igual(linha.preco_hoje, preco)
        or not _igual(linha.cambio_hoje, cambio)
        or not _igual(linha.valor_corrigido, corrigido)
    )
    return Plano(linha=linha, corrigido=corrigido, precisa_gravar=precisa)


def _igual(atual: float | None, novo: float) -> bool:
    return atual is not None and abs(atual - novo) < TOLERANCIA


class PlataformaESPP(Plataforma):
    nome = "ESPP"

    def __init__(
        self,
        cliente: notion.ClienteNotion,
        database_id: str,
        pagina_id: str | None = None,
        ticker: str = TICKER,
    ) -> None:
        self._cliente = cliente
        self._database_id = database_id
        self._pagina_id = pagina_id
        self._ticker = ticker
        self._linhas: list[Linha] = []

    # ------------------------------------------------------------- esteira

    def carregar(self) -> int:
        self._linhas = [ler_linha(p) for p in self._cliente.paginas(self._database_id)]
        return len(self._linhas)

    def requisitos(self) -> Requisitos:
        datas = [linha.data for linha in self._linhas if linha.data]
        return Requisitos(
            data_mais_antiga=min(datas) if datas else None,
            tickers=frozenset({self._ticker}),
            precisa_cdi=True,
            precisa_cambio=True,
        )

    def atualizar(self, contexto: Contexto, dry_run: bool = False) -> Resultado:
        preco = round(contexto.preco(self._ticker), calculos.CASAS_DINHEIRO)
        cambio = round(contexto.cambio(), calculos.CASAS_CAMBIO)

        planos = [
            p
            for p in (montar_plano(linha, contexto.cdi, preco, cambio) for linha in self._linhas)
            if p
        ]
        planos.sort(key=lambda p: p.linha.data or date.min)

        self._relatorio(planos, preco, cambio)
        self._sincronizar_resumo(dry_run)

        if dry_run:
            pendentes = sum(1 for p in planos if p.precisa_gravar)
            log.info("dry-run: nada gravado no ESPP (%d linha(s) mudariam).", pendentes)
            return Resultado(self.nome, len(planos), 0)

        gravadas = 0
        for plano in planos:
            if not plano.precisa_gravar:
                continue
            self._gravar(plano, preco, cambio, contexto.hoje)
            gravadas += 1
            log.info("Atualizada: %s", plano.linha.nome or plano.linha.page_id)

        log.info("ESPP: %d atualizada(s), %d sem mudanca.", gravadas, len(planos) - gravadas)
        return Resultado(self.nome, len(planos), gravadas)

    # -------------------------------------------------------------- escrita

    def _gravar(self, plano: Plano, preco: float, cambio: float, hoje: date) -> None:
        self._cliente.atualizar(
            plano.linha.page_id,
            {
                PROP_PRECO_HOJE: notion.valor_numero(preco),
                PROP_CAMBIO_HOJE: notion.valor_numero(cambio),
                PROP_CORRIGIDO: notion.valor_numero(plano.corrigido),
                PROP_ATUALIZADO: notion.valor_data(hoje),
            },
        )

    def _sincronizar_resumo(self, dry_run: bool) -> None:
        """Liga os lancamentos a pagina ESPP, senao os rollups dela ignoram os novos."""
        if not self._pagina_id:
            log.debug("Sem ID da pagina ESPP - resumo nao sincronizado.")
            return

        atuais = notion.relacao(
            self._cliente.pagina(self._pagina_id).get("properties", {}), PROP_LANCAMENTOS
        )
        desejados = [linha.page_id for linha in self._linhas]
        if atuais == set(desejados):
            log.info("Resumo: relacao ja estava em dia.")
            return

        diferenca = len(set(desejados) ^ atuais)
        if not dry_run:
            self._cliente.atualizar(
                self._pagina_id, {PROP_LANCAMENTOS: notion.valor_relacao(desejados)}
            )
        log.info("Resumo: %d lancamento(s) entraram/sairam da relacao.", diferenca)

    # ------------------------------------------------------------ relatorio

    def _relatorio(self, planos: list[Plano], preco: float, cambio: float) -> None:
        """Imprime o que o Notion deveria estar exibindo, para conferencia."""
        print(f"\n=== {self.nome} ===")
        print(f"{self._ticker} hoje: US$ {preco:,.2f}   |   Cambio hoje: R$ {cambio:,.4f}\n")

        cabecalho = (
            f"{'Linha':<22}{'Descontado':>12}{'Corrigido':>12}{'Acoes':>11}"
            f"{'Atual US$':>12}{'Atual R$':>12}{'Lucro R$':>12}{'Lucro corr.':>13}"
        )
        print(cabecalho)
        print("-" * len(cabecalho))

        total_acoes = total_atual = total_lucro = total_lucro_corr = 0.0

        for plano in planos:
            linha = plano.linha
            resultado = calculos.calcular(
                tipo=linha.tipo,
                valor_descontado=linha.valor_descontado or 0.0,
                valor_corrigido=plano.corrigido,
                taxa=linha.taxa or 0.0,
                dolar_comprado=linha.dolar_comprado or 0.0,
                preco_compra_desc=linha.preco_compra_desc or 0.0,
                preco_hoje=preco,
                cambio_hoje=cambio,
            )

            total_acoes += resultado.acoes
            total_atual += resultado.atual_brl
            total_lucro += resultado.lucro
            total_lucro_corr += resultado.lucro_corrigido

            print(
                f"{'*' if plano.precisa_gravar else ' '}{(linha.nome or '?'):<21}"
                f"{(linha.valor_descontado or 0):>12,.2f}"
                f"{plano.corrigido:>12,.2f}"
                f"{resultado.acoes:>11.5f}"
                f"{resultado.atual_usd:>12,.2f}"
                f"{resultado.atual_brl:>12,.2f}"
                f"{resultado.lucro:>12,.2f}"
                f"{resultado.lucro_corrigido:>13,.2f}"
            )

        print("-" * len(cabecalho))
        print(
            f"{'TOTAL':<22}{'':>12}{'':>12}{total_acoes:>11.5f}{'':>12}"
            f"{total_atual:>12,.2f}{total_lucro:>12,.2f}{total_lucro_corr:>13,.2f}"
        )
        print("\n(* = linha que a automacao vai gravar)\n")

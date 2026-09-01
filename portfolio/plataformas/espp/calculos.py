"""Espelho em Python das formulas que rodam dentro do Notion, no ESPP.

O Notion e quem calcula essas colunas de verdade. Este modulo existe para dois
usos: mostrar no relatorio o que a tabela deveria estar exibindo, e permitir
testar a matematica contra os numeros da planilha antiga sem depender de rede.

Se alterar uma formula no Notion, altere aqui tambem (e vice-versa).
"""

from __future__ import annotations

from dataclasses import dataclass

DESCONTO_ESPP = 0.15
TIPO_DIVIDENDO = "Reinvestimento de dividendo"

CASAS_DINHEIRO = 2
CASAS_CAMBIO = 4
CASAS_ACOES = 5
CASAS_INVESTIDO = 4  # dividendo reinvestido tem centavo quebrado; 2 casas distorcem


def valor_investido(dolar_comprado: float, taxa: float) -> float:
    return round(dolar_comprado - taxa, CASAS_INVESTIDO)


def cambio_na_compra(valor_descontado: float, investido: float) -> float:
    if investido == 0:
        return 0.0
    return round(valor_descontado / investido, CASAS_CAMBIO)


def preco_mercado_na_data(preco_compra_desc: float, tipo: str | None) -> float:
    """Preco cheio da acao na data.

    Compra via folha: o preco pago ja vem com 15% de desconto, entao o preco de
    mercado e o pago dividido por 0,85. Reinvestimento de dividendo nao tem
    desconto: o preco pago e o proprio preco de mercado.
    """
    if tipo == TIPO_DIVIDENDO:
        return preco_compra_desc
    return round(preco_compra_desc / (1 - DESCONTO_ESPP), CASAS_DINHEIRO)


def acoes_compradas(investido: float, preco_compra_desc: float) -> float:
    if preco_compra_desc == 0:
        return 0.0
    return round(investido / preco_compra_desc, CASAS_ACOES)


def valor_atual_usd(acoes: float, preco_hoje: float) -> float:
    return round(acoes * preco_hoje, CASAS_DINHEIRO)


def valor_atual_brl(acoes: float, preco_hoje: float, cambio_hoje: float) -> float:
    return round(acoes * preco_hoje * cambio_hoje, CASAS_DINHEIRO)


def lucro(atual_brl: float, custo_brl: float) -> float:
    return round(atual_brl - custo_brl, CASAS_DINHEIRO)


@dataclass(frozen=True)
class Resultado:
    investido: float
    cambio_compra: float
    preco_mercado: float
    acoes: float
    atual_usd: float
    atual_brl: float
    lucro: float
    lucro_corrigido: float


def calcular(
    *,
    tipo: str | None,
    valor_descontado: float,
    valor_corrigido: float,
    taxa: float,
    dolar_comprado: float,
    preco_compra_desc: float,
    preco_hoje: float,
    cambio_hoje: float,
) -> Resultado:
    """Roda a cadeia inteira, na mesma ordem e com os mesmos arredondamentos do Notion."""
    investido = valor_investido(dolar_comprado, taxa)
    acoes = acoes_compradas(investido, preco_compra_desc)
    atual_brl = valor_atual_brl(acoes, preco_hoje, cambio_hoje)

    return Resultado(
        investido=investido,
        cambio_compra=cambio_na_compra(valor_descontado, investido),
        preco_mercado=preco_mercado_na_data(preco_compra_desc, tipo),
        acoes=acoes,
        atual_usd=valor_atual_usd(acoes, preco_hoje),
        atual_brl=atual_brl,
        lucro=lucro(atual_brl, valor_descontado),
        lucro_corrigido=lucro(atual_brl, valor_corrigido),
    )

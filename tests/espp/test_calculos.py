"""Confere a matematica do ESPP contra as 9 linhas da planilha antiga (dados reais).

Snapshot usado na planilha: IBM US$ 231,51 e cambio R$ 5,15789875.
"""

import pytest

from portfolio.plataformas.espp import calculos

PRECO_HOJE = 231.51
CAMBIO_HOJE = 5.15789875

PAYROLL = "Compra payroll"
DIVIDENDO = "Reinvestimento de dividendo"

# nome, tipo, descontado, taxa, dolar_comprado, preco_c_desconto,
# esperado: acoes, atual_usd, atual_brl, lucro
PLANILHA = [
    ("Compra 01/2026", PAYROLL, 472.53, 6.0, 91.16, 258.20, 0.32982, 76.36, 393.84, -78.69),
    ("Compra 02/2026", PAYROLL, 472.53, 0.0, 91.86, 201.79, 0.45523, 105.39, 543.59, 71.06),
    ("Dividendo 03/2026", DIVIDENDO, 0.0, 0.0, 0.3755, 252.0315, 0.00149, 0.34, 1.78, 1.78),
    ("Compra 03/2026", PAYROLL, 472.53, 0.0, 90.22, 203.68, 0.44295, 102.55, 528.93, 56.40),
    ("Compra 04/2026", PAYROLL, 472.53, 0.0, 94.74, 194.02, 0.48830, 113.05, 583.08, 110.55),
    ("Compra 05/2026", PAYROLL, 472.53, 0.0, 93.42, 244.10, 0.38271, 88.60, 457.00, -15.53),
    ("Dividendo 06/2026", DIVIDENDO, 0.0, 0.0, 1.9909, 272.347, 0.00731, 1.69, 8.73, 8.73),
    ("Compra 06/2026", PAYROLL, 472.53, 0.0, 91.41, 243.62, 0.37522, 86.87, 448.05, -24.48),
    ("Compra 07/2026", PAYROLL, 658.04, 6.0, 128.48, 187.58, 0.65295, 151.16, 779.69, 121.65),
]


@pytest.mark.parametrize(
    "nome,tipo,descontado,taxa,dolar,preco_desc,acoes,atual_usd,atual_brl,lucro", PLANILHA
)
def test_bate_com_a_planilha(
    nome, tipo, descontado, taxa, dolar, preco_desc, acoes, atual_usd, atual_brl, lucro
):
    resultado = calculos.calcular(
        tipo=tipo,
        valor_descontado=descontado,
        valor_corrigido=descontado,  # CDI ainda nao aplicado, igual ao estado da planilha
        taxa=taxa,
        dolar_comprado=dolar,
        preco_compra_desc=preco_desc,
        preco_hoje=PRECO_HOJE,
        cambio_hoje=CAMBIO_HOJE,
    )

    assert resultado.acoes == acoes, nome
    assert resultado.atual_usd == atual_usd, nome
    assert resultado.atual_brl == atual_brl, nome
    assert resultado.lucro == lucro, nome


def test_totais_batem_com_o_total_da_planilha():
    acoes = atual_brl = 0.0
    for _, tipo, descontado, taxa, dolar, preco_desc, *_esperado in PLANILHA:
        resultado = calculos.calcular(
            tipo=tipo,
            valor_descontado=descontado,
            valor_corrigido=descontado,
            taxa=taxa,
            dolar_comprado=dolar,
            preco_compra_desc=preco_desc,
            preco_hoje=PRECO_HOJE,
            cambio_hoje=CAMBIO_HOJE,
        )
        acoes += resultado.acoes
        atual_brl += resultado.atual_brl

    assert round(acoes, 5) == 3.13598
    assert round(atual_brl, 2) == 3744.69


def test_compra_payroll_faz_gross_up_do_desconto():
    # US$ 258,20 pagos com 15% de desconto => preco cheio de US$ 303,76.
    assert calculos.preco_mercado_na_data(258.20, PAYROLL) == 303.76


def test_dividendo_nao_tem_desconto():
    # Reinvestimento compra a preco de mercado: preco pago = preco de mercado.
    assert calculos.preco_mercado_na_data(252.0315, DIVIDENDO) == 252.0315


def test_cambio_na_compra_e_o_efetivo():
    # R$ 472,53 viraram US$ 85,16 => R$ 5,5487 por dolar.
    assert calculos.cambio_na_compra(472.53, 85.16) == 5.5487


def test_sem_divisao_por_zero():
    assert calculos.cambio_na_compra(0.0, 0.0) == 0.0
    assert calculos.acoes_compradas(0.0, 0.0) == 0.0


def test_lucro_corrigido_usa_o_valor_corrigido():
    resultado = calculos.calcular(
        tipo=PAYROLL,
        valor_descontado=472.53,
        valor_corrigido=500.00,  # como se o CDI tivesse corrigido para R$ 500
        taxa=6.0,
        dolar_comprado=91.16,
        preco_compra_desc=258.20,
        preco_hoje=PRECO_HOJE,
        cambio_hoje=CAMBIO_HOJE,
    )

    assert resultado.lucro == -78.69
    assert resultado.lucro_corrigido == round(393.84 - 500.00, 2)


def test_casas_decimais_do_padrao_financeiro():
    resultado = calculos.calcular(
        tipo=PAYROLL,
        valor_descontado=472.53,
        valor_corrigido=472.53,
        taxa=0.0,
        dolar_comprado=93.42,
        preco_compra_desc=244.10,
        preco_hoje=PRECO_HOJE,
        cambio_hoje=CAMBIO_HOJE,
    )

    assert _casas(resultado.acoes) <= 5
    assert _casas(resultado.cambio_compra) <= 4
    for valor in (resultado.atual_usd, resultado.atual_brl, resultado.lucro, resultado.preco_mercado):
        assert _casas(valor) <= 2, valor


def _casas(valor: float) -> int:
    texto = f"{valor!r}"
    return len(texto.split(".")[1]) if "." in texto else 0

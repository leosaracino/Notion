"""Correcao pelo CDI (sem rede)."""

from datetime import date

import pytest

from portfolio.core import cdi

# Formato exato que o BCB devolve na serie 12 (CDI em % ao dia).
RESPOSTA_BCB = [
    {"data": "02/01/2026", "valor": "0.052531"},
    {"data": "05/01/2026", "valor": "0.052531"},
    {"data": "06/01/2026", "valor": "0.052531"},
]


def test_parse_serie_converte_e_ordena():
    serie = cdi.parse_serie(reversed(RESPOSTA_BCB))

    assert serie[0] == (date(2026, 1, 2), 0.052531)
    assert [dia for dia, _ in serie] == sorted(dia for dia, _ in serie)


def test_fator_ignora_o_dia_da_compra():
    serie = cdi.parse_serie(RESPOSTA_BCB)

    # Comprou em 02/01: so 05/01 e 06/01 rendem.
    esperado = (1 + 0.052531 / 100) ** 2
    assert cdi.fator_acumulado(serie, date(2026, 1, 2)) == pytest.approx(esperado)


def test_fator_considera_todos_os_dias_posteriores():
    serie = cdi.parse_serie(RESPOSTA_BCB)

    esperado = (1 + 0.052531 / 100) ** 3
    assert cdi.fator_acumulado(serie, date(2025, 12, 31)) == pytest.approx(esperado)


def test_fator_respeita_data_final():
    serie = cdi.parse_serie(RESPOSTA_BCB)

    esperado = 1 + 0.052531 / 100
    assert cdi.fator_acumulado(serie, date(2026, 1, 2), ate=date(2026, 1, 5)) == esperado


def test_fator_um_quando_nao_ha_dia_posterior():
    serie = cdi.parse_serie(RESPOSTA_BCB)

    assert cdi.fator_acumulado(serie, date(2026, 6, 30)) == 1.0


def test_corrigir_arredonda_para_centavos():
    serie = cdi.parse_serie(RESPOSTA_BCB)

    corrigido = cdi.corrigir(472.53, serie, date(2026, 1, 2))

    assert corrigido == round(472.53 * (1 + 0.052531 / 100) ** 2, 2)
    assert corrigido > 472.53


def test_corrigir_sem_serie_mantem_o_valor():
    assert cdi.corrigir(472.53, [], date(2026, 1, 2)) == 472.53


def test_intervalo_invertido_nao_busca_nada():
    assert cdi.buscar_serie(desde=date(2026, 9, 1), ate=date(2026, 1, 1)) == []


def test_intervalo_longo_e_quebrado_em_blocos(monkeypatch):
    # O SGS recusa series diarias muito longas, entao 20 anos viram 3 requisicoes.
    blocos = []

    def falso_bloco(inicio, fim, serie):
        blocos.append((inicio, fim))
        return []

    monkeypatch.setattr(cdi, "_buscar_bloco", falso_bloco)
    cdi.buscar_serie(desde=date(2006, 1, 1), ate=date(2026, 1, 1))

    assert len(blocos) == 3
    assert blocos[0][0] == date(2006, 1, 1)
    assert blocos[-1][1] == date(2026, 1, 1)
    # Sem buracos nem sobreposicao entre os blocos.
    for anterior, seguinte in zip(blocos, blocos[1:]):
        assert (seguinte[0] - anterior[1]).days == 1

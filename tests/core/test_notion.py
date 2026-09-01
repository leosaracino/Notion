"""Leitores e escritores de propriedade do Notion (sem rede)."""

from datetime import date

from portfolio.core import notion

PROPS = {
    "Nome": {"title": [{"plain_text": "Compra 01/"}, {"plain_text": "2026"}]},
    "Data da compra": {"date": {"start": "2026-01-30"}},
    "Tipo": {"select": {"name": "Compra payroll"}},
    "Valor descontado (BRL)": {"number": 472.53},
    "Lançamentos": {"relation": [{"id": "a"}, {"id": "b"}]},
}


def test_titulo_junta_os_pedacos():
    assert notion.titulo(PROPS, "Nome") == "Compra 01/2026"


def test_data():
    assert notion.data(PROPS, "Data da compra") == date(2026, 1, 30)


def test_selecao():
    assert notion.selecao(PROPS, "Tipo") == "Compra payroll"


def test_numero():
    assert notion.numero(PROPS, "Valor descontado (BRL)") == 472.53


def test_relacao():
    assert notion.relacao(PROPS, "Lançamentos") == {"a", "b"}


def test_propriedade_ausente_vira_vazio():
    assert notion.titulo({}, "Nome") == ""
    assert notion.numero({}, "Valor") is None
    assert notion.selecao({}, "Tipo") is None
    assert notion.data({}, "Data") is None
    assert notion.relacao({}, "Lançamentos") == set()


def test_propriedade_preenchida_com_nulo():
    vazias = {"Data": {"date": None}, "Tipo": {"select": None}, "Valor": {"number": None}}

    assert notion.data(vazias, "Data") is None
    assert notion.selecao(vazias, "Tipo") is None
    assert notion.numero(vazias, "Valor") is None


def test_escritores():
    assert notion.valor_numero(231.51) == {"number": 231.51}
    assert notion.valor_data(date(2026, 9, 1)) == {"date": {"start": "2026-09-01"}}
    assert notion.valor_relacao(["a", "b"]) == {"relation": [{"id": "a"}, {"id": "b"}]}

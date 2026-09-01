"""Plataforma ESPP: leitura das linhas, decisao do que gravar e resumo (sem rede)."""

from datetime import date

from portfolio.core import cdi
from portfolio.core.pipeline import Contexto
from portfolio.plataformas.espp.plataforma import Linha, PlataformaESPP, ler_linha, montar_plano

SERIE = cdi.parse_serie(
    [
        {"data": "02/02/2026", "valor": "0.052531"},
        {"data": "03/02/2026", "valor": "0.052531"},
    ]
)

PRECO = 231.51
CAMBIO = 5.1579
CORRIGIDO = round(472.53 * (1 + 0.052531 / 100) ** 2, 2)


class ClienteFalso:
    """Substitui o ClienteNotion: paginas fixas e registro do que foi gravado."""

    def __init__(self, paginas_db=(), pagina_espp=None):
        self._paginas_db = list(paginas_db)
        self._pagina_espp = pagina_espp or {"id": "pagina-espp", "properties": {}}
        self.gravacoes = []

    def paginas(self, database_id):
        return iter(self._paginas_db)

    def pagina(self, page_id):
        return self._pagina_espp

    def atualizar(self, page_id, propriedades):
        self.gravacoes.append((page_id, propriedades))


def linha(**campos) -> Linha:
    base = dict(
        page_id="pagina-1",
        nome="Compra 01/2026",
        data=date(2026, 1, 30),
        tipo="Compra payroll",
        valor_descontado=472.53,
        valor_corrigido=None,
        taxa=6.0,
        dolar_comprado=91.16,
        preco_compra_desc=258.2,
        preco_hoje=None,
        cambio_hoje=None,
    )
    base.update(campos)
    return Linha(**base)


def pagina_notion(page_id="pagina-1", **props):
    base = {
        "Nome": {"title": [{"plain_text": "Compra 01/2026"}]},
        "Data da compra": {"date": {"start": "2026-01-30"}},
        "Tipo": {"select": {"name": "Compra payroll"}},
        "Valor descontado (BRL)": {"number": 472.53},
        "Taxa (USD)": {"number": 6},
        "Dólar comprado (USD)": {"number": 91.16},
        "Preço de compra c/ desconto (USD)": {"number": 258.2},
    }
    base.update(props)
    return {"id": page_id, "properties": base}


# ---------------------------------------------------------------------- leitura


def test_ler_linha():
    lida = ler_linha(pagina_notion())

    assert lida.nome == "Compra 01/2026"
    assert lida.data == date(2026, 1, 30)
    assert lida.tipo == "Compra payroll"
    assert lida.dolar_comprado == 91.16
    assert lida.preco_hoje is None


# ----------------------------------------------------------------------- plano


def test_linha_sem_data_e_ignorada():
    assert montar_plano(linha(data=None), SERIE, PRECO, CAMBIO) is None


def test_compra_recebe_valor_corrigido_pelo_cdi():
    plano = montar_plano(linha(), SERIE, PRECO, CAMBIO)

    assert plano.corrigido == CORRIGIDO
    assert plano.precisa_gravar is True


def test_dividendo_fica_com_corrigido_zero():
    plano = montar_plano(
        linha(tipo="Reinvestimento de dividendo", valor_descontado=0.0), SERIE, PRECO, CAMBIO
    )

    assert plano.corrigido == 0.0


def test_nao_grava_quando_nada_mudou():
    plano = montar_plano(
        linha(preco_hoje=PRECO, cambio_hoje=CAMBIO, valor_corrigido=CORRIGIDO),
        SERIE,
        PRECO,
        CAMBIO,
    )

    assert plano.precisa_gravar is False


def test_grava_quando_o_preco_mudou():
    plano = montar_plano(
        linha(preco_hoje=230.00, cambio_hoje=CAMBIO, valor_corrigido=CORRIGIDO),
        SERIE,
        PRECO,
        CAMBIO,
    )

    assert plano.precisa_gravar is True


# -------------------------------------------------------------------- esteira


def contexto():
    return Contexto(hoje=date(2026, 9, 1), precos={"IBM": PRECO}, cambio_usd_brl=CAMBIO, cdi=SERIE)


def test_requisitos_declaram_a_compra_mais_antiga_e_o_ticker():
    cliente = ClienteFalso([pagina_notion("a"), pagina_notion("b", **{"Data da compra": {"date": {"start": "2026-07-31"}}})])
    plataforma = PlataformaESPP(cliente, "db")
    plataforma.carregar()

    req = plataforma.requisitos()

    assert req.data_mais_antiga == date(2026, 1, 30)
    assert req.tickers == frozenset({"IBM"})
    assert req.precisa_cdi and req.precisa_cambio


def test_atualiza_grava_as_quatro_colunas_da_automacao():
    cliente = ClienteFalso([pagina_notion("a")])
    plataforma = PlataformaESPP(cliente, "db")
    plataforma.carregar()

    resultado = plataforma.atualizar(contexto())

    assert resultado.atualizadas == 1
    page_id, props = cliente.gravacoes[0]
    assert page_id == "a"
    assert props["Preço IBM hoje (USD)"] == {"number": PRECO}
    assert props["Câmbio hoje (USD/BRL)"] == {"number": CAMBIO}
    assert props["Valor descontado corrigido (BRL)"] == {"number": CORRIGIDO}
    assert props["Última atualização"] == {"date": {"start": "2026-09-01"}}


def test_dry_run_nao_grava_nada():
    cliente = ClienteFalso([pagina_notion("a")], pagina_espp={"id": "p", "properties": {}})
    plataforma = PlataformaESPP(cliente, "db", pagina_id="p")
    plataforma.carregar()

    resultado = plataforma.atualizar(contexto(), dry_run=True)

    assert resultado.atualizadas == 0
    assert cliente.gravacoes == []


def test_liga_lancamentos_novos_a_pagina_de_resumo():
    cliente = ClienteFalso(
        [pagina_notion("a"), pagina_notion("b")],
        pagina_espp={"id": "p", "properties": {"Lançamentos": {"relation": [{"id": "a"}]}}},
    )
    plataforma = PlataformaESPP(cliente, "db", pagina_id="p")
    plataforma.carregar()
    plataforma.atualizar(contexto())

    relacao = [props for page_id, props in cliente.gravacoes if page_id == "p"]
    assert relacao == [{"Lançamentos": {"relation": [{"id": "a"}, {"id": "b"}]}}]


def test_nao_reescreve_relacao_ja_em_dia():
    cliente = ClienteFalso(
        [pagina_notion("a")],
        pagina_espp={"id": "p", "properties": {"Lançamentos": {"relation": [{"id": "a"}]}}},
    )
    plataforma = PlataformaESPP(cliente, "db", pagina_id="p")
    plataforma.carregar()
    plataforma.atualizar(contexto())

    assert [page_id for page_id, _ in cliente.gravacoes] == ["a"]


def test_sem_pagina_de_resumo_nao_quebra():
    cliente = ClienteFalso([pagina_notion("a")])
    plataforma = PlataformaESPP(cliente, "db", pagina_id=None)
    plataforma.carregar()

    assert plataforma.atualizar(contexto()).atualizadas == 1

"""A esteira: agregacao de requisitos e ordem de execucao (sem rede)."""

from datetime import date

import pytest

from portfolio.core import pipeline
from portfolio.core.pipeline import Contexto, Plataforma, Requisitos, Resultado


class PlataformaFalsa(Plataforma):
    def __init__(self, nome, requisitos, linhas=1):
        self.nome = nome
        self._requisitos = requisitos
        self._linhas = linhas
        self.contexto_recebido = None

    def carregar(self):
        return self._linhas

    def requisitos(self):
        return self._requisitos

    def atualizar(self, contexto, dry_run=False):
        self.contexto_recebido = contexto
        return Resultado(self.nome, self._linhas, 0)


def test_junta_pega_a_data_mais_antiga_de_toda_a_base():
    junto = pipeline.juntar(
        [
            Requisitos(data_mais_antiga=date(2026, 1, 30), precisa_cdi=True),
            Requisitos(data_mais_antiga=date(2021, 5, 10), precisa_cdi=True),
            Requisitos(data_mais_antiga=date(2024, 3, 1)),
        ]
    )

    assert junto.data_mais_antiga == date(2021, 5, 10)


def test_junta_unifica_tickers_sem_repetir():
    junto = pipeline.juntar(
        [
            Requisitos(tickers=frozenset({"IBM"})),
            Requisitos(tickers=frozenset({"ibm", "VALE3"})),
        ]
    )

    assert junto.tickers == frozenset({"IBM", "VALE3"})


def test_junta_liga_cdi_e_cambio_se_alguem_precisar():
    junto = pipeline.juntar([Requisitos(), Requisitos(precisa_cdi=True)])

    assert junto.precisa_cdi is True
    assert junto.precisa_cambio is False


def test_junta_sem_datas_nao_quebra():
    assert pipeline.juntar([Requisitos(), Requisitos()]).data_mais_antiga is None


def test_coletar_busca_uma_vez_e_compartilha(monkeypatch):
    chamadas = {"precos": 0, "cambio": 0, "cdi": 0}

    def falsos_precos(tickers):
        chamadas["precos"] += 1
        return {t.upper(): 231.51 for t in tickers}

    def falso_cambio():
        chamadas["cambio"] += 1
        return 5.1579

    def falso_cdi(desde, ate=None):
        chamadas["cdi"] += 1
        assert desde == date(2021, 5, 10)  # data mais antiga da base
        return [(date(2021, 5, 11), 0.02)]

    monkeypatch.setattr(pipeline.quotes, "precos", falsos_precos)
    monkeypatch.setattr(pipeline.quotes, "cambio_usd_brl", falso_cambio)
    monkeypatch.setattr(pipeline.cdi_mod, "buscar_serie", falso_cdi)

    espp = PlataformaFalsa(
        "ESPP",
        Requisitos(date(2026, 1, 30), frozenset({"IBM"}), precisa_cdi=True, precisa_cambio=True),
    )
    renda = PlataformaFalsa("Renda fixa", Requisitos(date(2021, 5, 10), precisa_cdi=True))

    pipeline.executar([espp, renda])

    assert chamadas == {"precos": 1, "cambio": 1, "cdi": 1}
    # As duas plataformas recebem exatamente o mesmo contexto.
    assert espp.contexto_recebido is renda.contexto_recebido


def test_executa_na_ordem_recebida(monkeypatch):
    ordem = []

    monkeypatch.setattr(pipeline.quotes, "precos", lambda t: {})
    monkeypatch.setattr(pipeline.quotes, "cambio_usd_brl", lambda: 5.0)

    class Registra(PlataformaFalsa):
        def atualizar(self, contexto, dry_run=False):
            ordem.append(self.nome)
            return super().atualizar(contexto, dry_run)

    pipeline.executar([Registra("ESPP", Requisitos()), Registra("Ações", Requisitos())])

    assert ordem == ["ESPP", "Ações"]


def test_plataforma_sem_linhas_e_ignorada(monkeypatch):
    monkeypatch.setattr(pipeline.quotes, "precos", lambda t: {})

    vazia = PlataformaFalsa("Ações", Requisitos(), linhas=0)
    cheia = PlataformaFalsa("ESPP", Requisitos())

    resultados = pipeline.executar([vazia, cheia])

    assert [r.plataforma for r in resultados] == ["ESPP"]
    assert vazia.contexto_recebido is None


def test_contexto_avisa_quando_o_dado_nao_foi_buscado():
    contexto = Contexto(hoje=date(2026, 9, 1))

    with pytest.raises(RuntimeError, match="IBM"):
        contexto.preco("IBM")
    with pytest.raises(RuntimeError, match="[Cc]ambio"):
        contexto.cambio()

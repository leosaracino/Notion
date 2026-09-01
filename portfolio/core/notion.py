"""Cliente do Notion e leitores de propriedade, compartilhados por todas as plataformas.

Nada aqui sabe o que e ESPP, acao ou renda fixa: e so ler paginas de uma
database, ler uma pagina e gravar propriedades.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Iterator

import requests

log = logging.getLogger(__name__)

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
TIMEOUT = 30


class ClienteNotion:
    def __init__(self, token: str, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            }
        )

    def paginas(self, database_id: str) -> Iterator[dict[str, Any]]:
        """Todas as paginas de uma database, seguindo a paginacao."""
        cursor: str | None = None
        while True:
            corpo: dict[str, Any] = {"page_size": 100}
            if cursor:
                corpo["start_cursor"] = cursor

            resp = self._session.post(
                f"{API}/databases/{database_id}/query", json=corpo, timeout=TIMEOUT
            )
            resp.raise_for_status()
            dados = resp.json()

            yield from dados["results"]

            if not dados.get("has_more"):
                return
            cursor = dados["next_cursor"]

    def pagina(self, page_id: str) -> dict[str, Any]:
        resp = self._session.get(f"{API}/pages/{page_id}", timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def atualizar(self, page_id: str, propriedades: dict[str, Any]) -> None:
        resp = self._session.patch(
            f"{API}/pages/{page_id}", json={"properties": propriedades}, timeout=TIMEOUT
        )
        resp.raise_for_status()


# ------------------------------------------------------ leitores de propriedade


def titulo(props: dict[str, Any], nome: str) -> str:
    prop = props.get(nome) or {}
    return "".join(parte.get("plain_text", "") for parte in prop.get("title", []))


def numero(props: dict[str, Any], nome: str) -> float | None:
    prop = props.get(nome) or {}
    return prop.get("number")


def selecao(props: dict[str, Any], nome: str) -> str | None:
    prop = props.get(nome) or {}
    escolhido = prop.get("select")
    return escolhido.get("name") if escolhido else None


def data(props: dict[str, Any], nome: str) -> date | None:
    prop = props.get(nome) or {}
    valor = prop.get("date")
    if not valor or not valor.get("start"):
        return None
    return datetime.fromisoformat(valor["start"][:10]).date()


def relacao(props: dict[str, Any], nome: str) -> set[str]:
    prop = props.get(nome) or {}
    return {item["id"] for item in prop.get("relation", [])}


# ------------------------------------------------------- escritores de valores


def valor_numero(valor: float) -> dict[str, Any]:
    return {"number": valor}


def valor_data(dia: date) -> dict[str, Any]:
    return {"date": {"start": dia.isoformat()}}


def valor_relacao(ids: list[str]) -> dict[str, Any]:
    return {"relation": [{"id": i} for i in ids]}

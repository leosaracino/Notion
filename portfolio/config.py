"""Configuracao lida de variaveis de ambiente (.env local ou Secrets do GitHub).

Cada plataforma tem seu bloco. Plataforma sem database configurada e ignorada
pela esteira — e assim que acoes e renda fixa entram, sem mexer no codigo comum.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # opcional: so ajuda no ambiente local
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:  # pragma: no cover - dependencia opcional
    pass


@dataclass(frozen=True)
class ConfigESPP:
    database_id: str
    pagina_id: str | None


@dataclass(frozen=True)
class Config:
    notion_token: str
    espp: ConfigESPP | None

    @classmethod
    def from_env(cls) -> "Config":
        token = os.environ.get("NOTION_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "NOTION_TOKEN nao configurado. No local use um arquivo .env; "
                "no CI use os Secrets do repositorio."
            )

        espp_database = os.environ.get("ESPP_DATABASE_ID", "").strip()
        espp = (
            ConfigESPP(
                database_id=espp_database,
                pagina_id=os.environ.get("ESPP_PAGE_ID", "").strip() or None,
            )
            if espp_database
            else None
        )

        if espp is None:
            raise RuntimeError("Nenhuma plataforma configurada (falta ESPP_DATABASE_ID).")

        return cls(notion_token=token, espp=espp)

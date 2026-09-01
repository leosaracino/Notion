"""Monta a esteira a partir da configuracao e roda pela linha de comando."""

from __future__ import annotations

import argparse
import logging

import requests

from .config import Config
from .core import pipeline
from .core.notion import ClienteNotion
from .plataformas.espp.plataforma import PlataformaESPP

log = logging.getLogger("portfolio")


def montar(config: Config) -> list[pipeline.Plataforma]:
    """Ordem da esteira: ESPP, depois acoes e renda fixa quando existirem."""
    cliente = ClienteNotion(config.notion_token, requests.Session())

    plataformas: list[pipeline.Plataforma] = []
    if config.espp:
        plataformas.append(
            PlataformaESPP(cliente, config.espp.database_id, config.espp.pagina_id)
        )
    return plataformas


def executar(dry_run: bool = False) -> int:
    resultados = pipeline.executar(montar(Config.from_env()), dry_run=dry_run)

    for resultado in resultados:
        log.info(
            "%s: %d linha(s), %d atualizada(s).",
            resultado.plataforma,
            resultado.linhas,
            resultado.atualizadas,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Atualiza as databases de investimento no Notion."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="calcula e imprime, mas nao escreve no Notion"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="log detalhado")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        return executar(dry_run=args.dry_run)
    except Exception as exc:
        log.error("Falhou: %s", exc)
        return 1

"""Utilitarios compartilhados pelos scripts operacionais."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from notion_client import Client

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

load_dotenv(ROOT / ".env")

DATA_SOURCE_ID = os.getenv("DATA_SOURCE_ID", "18f30ca2-d8ff-812f-a1da-000bac12114a")


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def notion_client() -> Client:
    return Client(auth=required_env("NOTION_TOKEN"))

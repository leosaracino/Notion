"""
Calculo retroativo para um titulo de renda fixa.

Uso:
    python scripts/backfill_renda_fixa.py <PAGE_ID>

Le data de Compra, Valor Aplicado e Taxa de aplicacao do card,
busca todo o historico de CDI desde a compra ate hoje, calcula
o produto acumulado e atualiza Valor Atual + Taxa Acumulada.
"""
import datetime
import sys
from decimal import Decimal

from dotenv import load_dotenv
load_dotenv()
import os
from notion_client import Client

# Reusa logica do modulo principal
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion import (  # type: ignore
    calcular_retroativo_cdi,
    formatar_taxa,
    calcular_ir_iof,
    _ler_valor_aplicado,
)

n = Client(auth=os.getenv("NOTION_TOKEN"))


def backfill(page_id: str) -> None:
    page = n.pages.retrieve(page_id=page_id)
    props = page["properties"]

    tipo = (props.get("Tipo", {}).get("select") or {}).get("name")
    valor_aplicado, campo_usado = _ler_valor_aplicado(props, "BR")
    if valor_aplicado is None:
        raise RuntimeError("Card sem Valor Aplicado")
    print(f"  Usando campo: {campo_usado}")
    taxa_aplicada = props["Taxa de aplicação"]["number"]
    data_compra = datetime.datetime.strptime(
        props["Compra"]["date"]["start"], "%Y-%m-%d"
    ).date()

    produto, valor_bruto = calcular_retroativo_cdi(
        valor_aplicado, data_compra, taxa_aplicada
    )

    ganho_bruto = valor_bruto - Decimal(str(valor_aplicado))
    dias = (datetime.date.today() - data_compra).days

    if tipo == "CDB":
        ir, iof = calcular_ir_iof(ganho_bruto, dias)
        ganho = ganho_bruto - ir - iof
        valor_final = valor_bruto - ir - iof
        print(f"  IR: {ir:.2f}, IOF: {iof:.2f}")
    else:
        ganho = ganho_bruto
        valor_final = valor_bruto

    rendimento = float(ganho / Decimal(str(valor_aplicado)))

    print(f"Card {tipo} | aplicado={valor_aplicado} taxa={taxa_aplicada} dias={dias}")
    print(f"  Produto acumulado: {produto}")
    print(f"  Valor bruto:       {valor_bruto}")
    print(f"  Ganho liquido:     {ganho}")
    print(f"  Valor final:       {valor_final}")
    print(f"  Rendimento:        {rendimento*100:.2f}%")

    n.pages.update(page_id=page_id, properties={
        "Rendimento": {"number": rendimento},
        "Ganho": {"number": float(ganho)},
        "Valor Atual": {"number": float(valor_final)},
        "Taxa Acumulada": {"rich_text": [{"text": {"content": formatar_taxa(produto)}}]},
    })
    print("OK")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/backfill_renda_fixa.py <PAGE_ID>")
        sys.exit(1)
    backfill(sys.argv[1])

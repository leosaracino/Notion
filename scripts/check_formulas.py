"""Mostra expressao das formulas no database."""
from dotenv import load_dotenv
load_dotenv()
import os
from notion_client import Client

n = Client(auth=os.getenv("NOTION_TOKEN"))
DS_ID = "18f30ca2-d8ff-812f-a1da-000bac12114a"
ds = n.data_sources.retrieve(data_source_id=DS_ID)

for name, prop in ds["properties"].items():
    if prop["type"] == "formula":
        expr = prop["formula"].get("expression", prop["formula"])
        print(f"{name}:")
        print(f"  {expr}\n")

# Pega um card real pra ver o valor calculado
res = n.data_sources.query(data_source_id=DS_ID)
for p in res.get("results", [])[:1]:
    print("=== Exemplo (primeiro card) ===")
    for name in ("Total", "Total compra", "Valor Aplicado", "Quantidade", "Valor Atual"):
        prop = p["properties"].get(name, {})
        t = prop.get("type")
        if t == "formula":
            val = prop["formula"]
            print(f"  {name}: {val}")
        elif t == "number":
            print(f"  {name}: {prop.get('number')}")

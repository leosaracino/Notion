"""Mostra expressao das formulas no database."""

from common import DATA_SOURCE_ID, notion_client

n = notion_client()
ds = n.data_sources.retrieve(data_source_id=DATA_SOURCE_ID)

for name, prop in ds["properties"].items():
    if prop["type"] == "formula":
        expr = prop["formula"].get("expression", prop["formula"])
        print(f"{name}:")
        print(f"  {expr}\n")

# Pega um card real pra ver o valor calculado
res = n.data_sources.query(data_source_id=DATA_SOURCE_ID)
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

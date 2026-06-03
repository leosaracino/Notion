"""Mostra estado completo do database Ativos."""

from common import DATA_SOURCE_ID, notion_client

n = notion_client()
ds = n.data_sources.retrieve(data_source_id=DATA_SOURCE_ID)

print("=" * 60)
print("ESTADO ATUAL DO DATABASE 'Ativos'")
print("=" * 60)

print("\n[CAMPOS (propriedades)]")
for name, prop in sorted(ds["properties"].items()):
    t = prop["type"]
    extra = ""
    if t == "select":
        opts = [o["name"] for o in prop["select"].get("options", [])]
        extra = f"  opcoes: {opts}"
    elif t == "number":
        fmt = prop["number"].get("format", "")
        extra = f"  formato: {fmt}"
    print(f"  {name:25s} [{t}]{extra}")

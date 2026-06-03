"""Mostra estado completo do database Ativos."""
from dotenv import load_dotenv
load_dotenv()
import os
from notion_client import Client

n = Client(auth=os.getenv("NOTION_TOKEN"))
DS_ID = "18f30ca2-d8ff-812f-a1da-000bac12114a"

ds = n.data_sources.retrieve(data_source_id=DS_ID)

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

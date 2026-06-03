"""Aplica mudancas de schema no database Ativos via API Notion."""
from dotenv import load_dotenv
import os
load_dotenv()
from notion_client import Client

n = Client(auth=os.getenv("NOTION_TOKEN"))
DS_ID = "18f30ca2-d8ff-812f-a1da-000bac12114a"

ds = n.data_sources.retrieve(data_source_id=DS_ID)
tipo_opts = ds["properties"]["Tipo"]["select"]["options"]

if "ESPP" not in {o["name"] for o in tipo_opts}:
    tipo_opts.append({"name": "ESPP", "color": "blue"})

updates = {
    "Tipo": {"select": {"options": tipo_opts}},
    "Mercado": {"select": {"options": [
        {"name": "BR", "color": "green"},
        {"name": "US", "color": "blue"},
    ]}},
    "Salario": {"number": {"format": "real"}},
    "Contribuicao Acumulada": {"number": {"format": "dollar"}},
    "Proxima Compra": {"date": {}},
}

result = n.data_sources.update(data_source_id=DS_ID, properties=updates)
print("Schema atualizado")
for name in updates:
    if name in result.get("properties", {}):
        print(f"  + {name}")

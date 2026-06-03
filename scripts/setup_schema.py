"""Aplica mudancas de schema no database Ativos via API Notion."""

from common import DATA_SOURCE_ID, notion_client

n = notion_client()

ds = n.data_sources.retrieve(data_source_id=DATA_SOURCE_ID)
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

result = n.data_sources.update(data_source_id=DATA_SOURCE_ID, properties=updates)
print("Schema atualizado")
for name in updates:
    if name in result.get("properties", {}):
        print(f"  + {name}")

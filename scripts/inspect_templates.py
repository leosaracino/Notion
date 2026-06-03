"""Tenta encontrar templates ja criados no database."""
from dotenv import load_dotenv
load_dotenv()
import os, json
from notion_client import Client

n = Client(auth=os.getenv("NOTION_TOKEN"))
DB_ID = os.getenv("DATABASE_ID")
DS_ID = "18f30ca2-d8ff-812f-a1da-000bac12114a"

# 1) Bloco pai - pode ter sub-paginas/templates como filhos
db = n.databases.retrieve(database_id=DB_ID)
parent_block_id = db["parent"]["block_id"]
print(f"Database 'Ativos' esta dentro do bloco: {parent_block_id}\n")

# 2) Lista todos os filhos do bloco pai (a pagina de investimentos)
try:
    children = n.blocks.children.list(block_id=parent_block_id)
    print(f"=== Filhos da pagina pai ({len(children['results'])} blocos) ===")
    for c in children["results"]:
        t = c.get("type")
        snippet = ""
        if t == "child_database":
            snippet = c.get("child_database", {}).get("title", "")
        elif t == "child_page":
            snippet = c.get("child_page", {}).get("title", "")
        elif t in ("heading_1", "heading_2", "heading_3", "paragraph", "bulleted_list_item"):
            rich = c.get(t, {}).get("rich_text", [])
            snippet = "".join(x.get("plain_text", "") for x in rich)[:80]
        print(f"  {t:20s} {snippet}")
except Exception as e:
    print(f"erro: {e}")

# 3) Tenta busca direta por blocos do database (templates ficam como filhos do database)
print(f"\n=== Filhos do DATABASE (templates ficam aqui) ===")
try:
    children = n.blocks.children.list(block_id=DB_ID)
    print(f"Total: {len(children.get('results', []))}")
    for c in children.get("results", []):
        print(f"  {c.get('type')}: {c.get('id')}")
except Exception as e:
    print(f"  (API nao retorna templates como blocos: {type(e).__name__})")

# 4) Query com archived=True para pegar tudo
print(f"\n=== Query data_source completo ===")
res = n.data_sources.query(data_source_id=DS_ID)
for p in res.get("results", []):
    title_prop = p["properties"].get("Ativo", {}).get("title", [])
    title = "".join(t.get("plain_text", "") for t in title_prop) or "(sem titulo)"
    tipo = (p["properties"].get("Tipo", {}).get("select") or {}).get("name", "-")
    is_tpl = p.get("is_template", False)
    archived = p.get("archived", False)
    flag = " [TEMPLATE]" if is_tpl else (" [ARQ]" if archived else "")
    print(f"  [{tipo:12s}] {title:30s}{flag}")

import sys
from dotenv import load_dotenv
load_dotenv()
import os
from notion_client import Client

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

try:
    n = Client(auth=os.getenv("NOTION_TOKEN"))
    DS_ID = "18f30ca2-d8ff-812f-a1da-000bac12114a"
    res = n.data_sources.query(data_source_id=DS_ID)
    print(f"Total cards: {len(res.get('results', []))}", flush=True)
    for p in res.get("results", []):
        props = p["properties"]
        title = "".join(t.get("plain_text", "") for t in props.get("Ativo", {}).get("title", []))
        out = [f"\n=== {title} ==="]
        for name in ("Valor Aplicado", "Quantidade", "Valor Atual", "Ganho", "Total compra", "Total"):
            prop = props.get(name, {})
            t = prop.get("type")
            if t == "formula":
                f = prop["formula"]
                val = f.get("number") or f.get("string") or f.get("boolean")
                out.append(f"  {name:18s} (formula) = {val}")
            elif t == "number":
                out.append(f"  {name:18s} = {prop.get('number')}")
        print("\n".join(out), flush=True)
except Exception as e:
    import traceback
    traceback.print_exc()

import sys

from common import DATA_SOURCE_ID, notion_client

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

try:
    n = notion_client()
    res = n.data_sources.query(data_source_id=DATA_SOURCE_ID)
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

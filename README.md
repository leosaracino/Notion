# Notion Portfolio Automation

Automacao Python para atualizar um portfolio de investimentos no Notion.

O projeto le cards do database `Ativos`, calcula cotacao/rendimento conforme
o tipo do ativo e escreve os resultados de volta no Notion. Tambem inclui um
dashboard estatico com widgets TradingView para embed no Notion.

## Estrutura

```text
.
├── src/notion_portfolio/       # pacote Python principal
│   ├── automation.py           # logica da automacao
│   └── __main__.py             # entrypoint: python -m notion_portfolio
├── scripts/                    # utilitarios operacionais e debug
├── frontend/                   # dashboard estatico TradingView
├── docs/context.md             # contexto historico e roadmap
├── .github/workflows/          # automacao no GitHub Actions
├── pyproject.toml              # definicao instalavel do projeto
├── requirements.txt            # dependencias para setup simples
└── .env.example                # variaveis de ambiente esperadas
```

## Setup local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
```

Preencha o `.env` com:

```text
NOTION_TOKEN=
DATABASE_ID=
DATA_SOURCE_ID=
BRAPI_TOKEN=
```

`DATA_SOURCE_ID` ja tem o valor conhecido no `.env.example`; altere apenas se
o database/data source mudar.

## Executar

```powershell
python -m notion_portfolio
```

Ou, apos `pip install -e .`:

```powershell
notion-portfolio
```

## Scripts uteis

```powershell
python scripts/status.py
python scripts/setup_schema.py
python scripts/backfill_renda_fixa.py <PAGE_ID>
python scripts/check_formulas.py
python scripts/decode_formulas.py
python scripts/inspect_templates.py
```

## GitHub Actions

O workflow `.github/workflows/notion-update.yml` roda em dias uteis as 22h BRT
e tambem pode ser disparado manualmente. Configure estes secrets no GitHub:

- `NOTION_TOKEN`
- `DATABASE_ID`
- `DATA_SOURCE_ID`
- `BRAPI_TOKEN`

`DATA_SOURCE_ID` e recomendado. Se ele nao existir, a automacao tenta descobrir
o primeiro data source a partir de `DATABASE_ID`.

## Dashboard

O dashboard esta em `frontend/index.html`. Ele e estatico e pode ser publicado
via GitHub Pages ou outro host simples, depois embedado no Notion.

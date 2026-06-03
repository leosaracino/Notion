# Contexto do Projeto — Automação Notion de Portfolio

Documento de referência sobre o estado atual do projeto, o que foi feito,
o que foi planejado e por quê.

---

## 1. O que o projeto faz

Automação Python que lê cards do database `Ativos` no Notion, calcula
o rendimento de cada investimento conforme seu tipo e escreve os
resultados de volta no Notion.

**Tipos suportados pelo código:**
- Ação (BR via brapi.dev / US via yfinance)
- LCA / LCI (CDI da série 4389 BCB, isento de IR/IOF)
- CDB (CDI + IR regressivo + IOF tabelado)
- ESPP (IBM Employee Stock Purchase Plan — versão placeholder)

**Tipos definidos no Notion mas ainda não processados:** Cripto, Fundo,
Tesouro Direto, FII. Roadmap futuro.

---

## 2. Estrutura do repositório

```
d:\Notion\Notion\
├── .env                      ← credenciais (fora do git)
├── .gitignore                ← ignora .env, venv, __pycache__
├── .env.example              ← modelo sem segredos
├── .github/
│   └── workflows/
│       └── notion-update.yml ← cron diário 22h BRT em dias úteis
├── pyproject.toml            ← projeto Python instalável
├── requirements.txt          ← dependências Python
├── README.md                 ← guia operacional
├── docs/
│   └── context.md            ← este documento
├── frontend/
│   └── index.html            ← dashboard frontend (8 widgets TradingView)
├── src/
│   └── notion_portfolio/
│       ├── automation.py     ← logica principal
│       └── __main__.py       ← entry point: python -m notion_portfolio
└── scripts/                  ← utilitários de uso ocasional
    ├── common.py             ← helper compartilhado dos scripts
    ├── setup_schema.py       ← aplica/atualiza schema do database
    ├── status.py             ← lista propriedades atuais
    ├── backfill_renda_fixa.py← recalcula 1 titulo retroativamente
    ├── inspect_templates.py  ← debug
    ├── check_formulas.py     ← debug formulas
    └── decode_formulas.py    ← decodifica IDs internos das formulas
```

**Por que essa organização:**
- `src/` contem codigo de **producao** em formato de pacote Python.
- `frontend/` contem o dashboard estatico.
- `docs/` contem contexto, historico e roadmap.
- `scripts/` contem **ferramentas operacionais** que rodam 1x ou ocasionalmente.
- `.github/workflows/` e caminho obrigatorio do GitHub Actions.
- `.env` nunca vai para o git, equivalente em CI/CD sao GitHub Secrets.

---

## 3. Bugs corrigidos no notion.py original

| # | Bug original | Correcao aplicada |
|---|---|---|
| 1 | IOF calculado por interpolacao linear (errado) | Tabela oficial dia-a-dia (lookup de 30 valores) |
| 2 | Feriados via `holidays.Brazil` + hardcode 2025/2026 | Biblioteca `anbima_calendar` (1969-2068, oficial mercado) |
| 3 | Check de dia util do CDB estava comentado | Centralizado em `_processar_renda_fixa()` |
| 4 | CDI consultado a cada card processado | `@lru_cache(maxsize=1)` busca uma vez por execucao |
| 5 | Tokens hardcoded no codigo fonte | Movidos para `.env` com `python-dotenv` |
| 6 | LCA/LCI e CDB duplicados | Funcao unica `_processar_renda_fixa(com_impostos)` |
| 7 | `print()` sem contexto | `logging` estruturado com niveis |
| 8 | Falta retry no CDI | 5 tentativas com backoff de 1s |

---

## 4. APIs em uso e validacao

| API | Uso | Status validado | Detalhes |
|---|---|---|---|
| `brapi.dev` | Cotacao de acoes BR | OK | Token gratis, +4000 ativos, real-time |
| BCB SGS serie 4389 | CDI anual % a.a. | OK | D-1, oficial, gratis, base 252 dias uteis |
| `yfinance` | Cotacao de acoes US (IBM, etc) | OK | Grátis, sem token, sem rate limit pratico |
| Notion API v2 | Read/write cards e schema | OK | Token de integracao + database compartilhado |

**Cálculo financeiro validado:**
- CDI diário = `(1 + cdi_anual/100)^(1/252) - 1` (formula oficial mercado BR)
- Calculo retroativo (script `backfill_renda_fixa.py`) busca todos os CDIs
  entre data de compra e hoje, multiplica os fatores em cascata.
  Teste: R$ 10.000 em 04/02/2025 a 100% CDI → R$ 11.907,96 hoje (19,08%).

---

## 5. Schema do database Notion `Ativos`

**Database:** "Ativos" (id `18f30ca2-d8ff-81ef-947b-f436db931bf2`).
**Data source id:** `18f30ca2-d8ff-812f-a1da-000bac12114a`.

### Propriedades atuais (19 campos)

| Campo | Tipo | Quem preenche | Observacao |
|---|---|---|---|
| Ativo | title | usuario | titulo do card |
| Tipo | select | usuario / template | CDB, Cripto, Fundo, Tesouro direto, FII, Acao, LCA/LCI, ESPP |
| Mercado | select | usuario / template | BR ou US |
| Indice | rich_text | usuario | ticker (VALE3, IBM, etc) |
| Corretora | select | usuario | Santander, Itau, Clear, XP, Rico |
| Valor Aplicado R$ | number (real) | usuario | usado para BR |
| Valor Aplicado  $ | number (dollar) | usuario | usado para US (atencao: 2 espacos no nome) |
| Valor Atual | number (real) | script | |
| Quantidade | number | usuario | |
| Taxa de aplicacao | number (percent) | usuario | % do CDI contratado (1.0 = 100%) |
| Taxa Acumulada | rich_text | script (comeca em "1") | produto acumulado do CDI |
| Rendimento | number (percent) | script | |
| Ganho | number (real) | script | |
| Compra | date | usuario | data de aquisicao |
| Vencimento | date | usuario | renda fixa |
| Salario | number (real) | usuario | ESPP |
| Contribuicao Acumulada | number (dollar) | usuario / script | ESPP |
| Proxima Compra | date | usuario / script | ESPP - proximo payday |
| Total compra | formula | auto | Valor Aplicado R$ * Quantidade |
| Total | formula | auto | Ganho + Total compra |

### Mudancas feitas no schema via API

- Adicionado `ESPP` ao select `Tipo`
- Criados campos `Mercado`, `Salario`, `Contribuicao Acumulada`, `Proxima Compra`
- Usuario manualmente desdobrou `Valor Aplicado` em `Valor Aplicado R$` e
  `Valor Aplicado  $` (codigo trata os 3 nomes possiveis)

---

## 6. Limitacoes descobertas da API do Notion

| Limitacao | Impacto |
|---|---|
| API nao expoe templates de database | Templates so podem ser criados pela UI |
| API nao permite criar views | Views so podem ser criadas pela UI |
| API nao permite criar botoes | Botoes so podem ser criados pela UI |
| Visibilidade de propriedade e a nivel de database, nao por template | Nao da para mostrar Salario so em ESPP e esconder em CDB |

**Consequencia pratica:** estrategia escolhida e usar `Ocultar quando vazio`
globalmente. Cada card so mostra os campos que tem valor, naturalmente
diferenciando os tipos.

---

## 7. IBM ESPP — entendimento atual

**Detalhes do plano (pesquisados):**
- Desconto de **15%** sobre o preco da acao (mudou em 01/04/2022 de 5% para 15%)
- Contribuicao maxima de **10% do salario eligivel**
- Limite anual de USD 25.000 em valor de compra
- Periodos de oferta de **6 meses** (1 jan e 1 jul)
- Compras de fato ocorrem **a cada periodo de pagamento** dentro da janela
  (mensal/quinzenal conforme folha)
- **Lookback feature:** preco da compra = menor entre
  `0.85 * preco_inicio_oferta` e `0.85 * preco_data_compra`

**Codigo atual:** placeholder simples — apenas atualiza valor de mercado
da posicao usando yfinance. Logica completa de acumulacao mensal +
lookback semestral ainda nao implementada (`Atualizar ESPP com logica
mensal + lookback` no roadmap).

---

## 8. Frontend (`frontend/index.html`)

Dashboard de **8 widgets TradingView** em tema escuro, embedavel no Notion:

```
- Ticker Tape (10 ativos rolando)
- Market Overview (3 tabs: Brasil / EUA / Cripto-Cambio)
- Stock Heatmap IBOV (setores por variacao)
- 4x Mini Symbol Overview (BOVA11, IBM, VALE3, PETR3)
- Advanced Chart IBOV (com EMA e RSI)
```

**Caracteristicas:**
- Responsivo (vira coluna unica em telas < 900px)
- Tema escuro consistente (#0a0a0a / #131313)
- Copyright TradingView escondido via CSS
- Apenas widgets nativos TradingView, sem JS proprio

---

## 9. Automacao (GitHub Actions)

Workflow `.github/workflows/notion-update.yml`:
- Instala o pacote com `pip install -e .`
- Roda `python -m notion_portfolio` automaticamente
- Cron: `0 1 * * 2-6` (UTC) = 22h BRT em dias uteis
- Tambem disparavel manualmente (`workflow_dispatch`)
- Le `NOTION_TOKEN`, `DATABASE_ID`, `DATA_SOURCE_ID`, `BRAPI_TOKEN` de Secrets do GitHub

**Secrets necessarios no repo:** valores ja estao no `.env` local,
precisam ser copiados para Settings -> Secrets and variables -> Actions.
`DATA_SOURCE_ID` e recomendado; se estiver ausente, o codigo tenta descobrir
o primeiro data source a partir de `DATABASE_ID`.

---

## 10. Roadmap / proximos passos

### Curto prazo (a fazer)

1. **Templates no Notion (UI)** - criar 5 templates pre-preenchendo so o `Tipo`:
   - Renda Fixa CDB, Renda Fixa LCA/LCI, Acao BR, Acao EUA, IBM ESPP
2. **Visibilidade global** - configurar `Ocultar quando vazio` em todas as
   propriedades opcionais (uma vez no database).
3. **Botoes "Adicionar Ativo"** - 5 botoes na pagina pai, cada um apontando
   para um template.
4. **Deploy do frontend/index.html** - GitHub Pages + embed no Notion.
5. **Cadastrar novos ativos** - recriar os 5 ativos que foram apagados.
6. **Rodar `python -m notion_portfolio`** e validar.

### Medio prazo

1. **ESPP completo** - implementar acumulacao mensal de salario + compra
   semestral com lookback (preco = min(0.85*inicio, 0.85*hoje)).
2. **Campos `Valor Atual R$` e `Valor Atual $`** - para consistencia com os
   dois Valor Aplicado existentes.
3. **Tesouro Direto** - integrar API ANBIMA para titulos publicos.
4. **FII** - usar brapi.dev (mesma logica de acao, IR diferente).
5. **Cripto** - integrar CoinGecko ou Binance.

### Longo prazo

1. **Dashboard custom** lendo dados do Notion (export JSON + frontend estatico).
2. **Alertas** por email/Telegram quando rendimento bate metas.
3. **Historico de patrimonio** com graficos de evolucao mensal.

---

## 11. Dependencias

`requirements.txt`:
- `notion-client>=2.2.0` - SDK oficial Notion
- `requests>=2.32.0` - HTTP para brapi e BCB
- `anbima-calendar>=0.1.1` - feriados oficiais mercado financeiro BR
- `python-dotenv>=1.0.0` - carrega .env
- `yfinance>=0.2.40` - cotacoes acoes US

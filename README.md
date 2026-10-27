# Automacao de investimentos no Notion

Esteira que mantem as databases de investimento do Notion atualizadas, rodando
3x por dia no GitHub Actions. O Notion continua sendo quem calcula as colunas
derivadas (formulas e rollups); o projeto so busca o que e externo a ele.

Hoje roda **ESPP**. `Ações` e `Renda fixa` entram depois, na mesma esteira.

## A esteira

```
1. cada plataforma carrega suas linhas do Notion e declara o que precisa
   (investimento mais antigo, tickers, se usa CDI e cambio)
2. a esteira junta tudo e busca UMA VEZ SO:
      CDI  -> desde o investimento mais antigo de toda a base
      preco -> um por ticker, mesmo que varias plataformas usem o mesmo
      cambio -> um
3. cada plataforma recebe esse contexto e atualiza o que e dela:
      ESPP  ->  Ações  ->  Renda fixa
```

Ou seja: o CDI que o ESPP usa para corrigir o valor descontado e o mesmo que a
renda fixa vai usar para render, e a IBM e buscada uma vez mesmo que apareca
tambem na carteira de acoes.

## Estrutura

```
portfolio/
  config.py                  variaveis de ambiente, um bloco por plataforma
  app.py                     monta a esteira e roda pela linha de comando
  core/                      comum a todas as plataformas
    notion.py                cliente do Notion + leitores/escritores de propriedade
    quotes.py                preco de acoes (dedup por ticker) e cambio USD/BRL
    cdi.py                   serie diaria do CDI (BCB SGS 12) e correcao acumulada
    pipeline.py              Requisitos, Contexto, Plataforma e a orquestracao
  plataformas/
    espp/
      calculos.py            espelho das formulas do Notion (relatorio + testes)
      plataforma.py          colunas do ESPP, o que gravar e o resumo da pagina
tests/
  core/                      testes do que e comum
  espp/                      testes do que e do ESPP
```

**Plataforma nova** = uma pasta em `plataformas/`, uma classe que implementa
`Plataforma` (`carregar` / `requisitos` / `atualizar`) e uma linha em
`app.montar`. Nada do `core/` precisa mudar.

## ESPP

A automacao escreve 4 colunas; o resto voce digita ou o Notion calcula.

| Coluna | De onde vem |
|---|---|
| `Preço IBM hoje (USD)` | Yahoo Finance (fallback: Stooq) |
| `Câmbio hoje (USD/BRL)` | AwesomeAPI (fallback: PTAX/BCB serie 1) |
| `Valor descontado corrigido (BRL)` | CDI diario composto desde a data da compra |
| `Última atualização` | data da execucao |

### Como cadastrar uma linha nova

**Compra via folha** (`Tipo = Compra payroll`): preencha `Data da compra`,
`Valor descontado (BRL)`, `Taxa (USD)`, `Dólar comprado (USD)` e
`Preço de compra c/ desconto (USD)`. O Notion deriva o resto:

```
Valor investido (USD)          = Dólar comprado − Taxa
Câmbio na compra               = Valor descontado ÷ Valor investido
Preço de mercado na data (USD) = Preço de compra c/ desconto ÷ 0,85
Ações compradas                = Valor investido ÷ Preço de compra c/ desconto
```

**Reinvestimento de dividendo** (`Tipo = Reinvestimento de dividendo`): mesmas
colunas, so que `Valor descontado (BRL)` e `Taxa (USD)` ficam em 0,
`Dólar comprado (USD)` recebe o valor do dividendo em USD e
`Preço de compra c/ desconto (USD)` recebe o preco pago na data. Como nao ha
desconto de 15% nesse caso, a formula de `Preço de mercado na data` olha o
`Tipo` e usa o preco pago direto, sem gross-up.

### Resumo no topo da pagina

Os totais sao propriedades da propria pagina ESPP, calculados por rollup sobre a
relacao `Lançamentos`:

| Propriedade | Soma qual coluna dos lancamentos |
|---|---|
| `Total Investido` | `Valor descontado (BRL)` — reais descontados da folha |
| `Total corrigido` | `Valor descontado corrigido (BRL)` |
| `Total investido` | `Valor investido (USD)` — dolares que viraram acao |
| `Ações hoje` | `Ações compradas` |
| `Valor atual (USD)` / `(BRL)` | `Valor atual` |
| `Lucro total (BRL)` | formula: `Valor atual (BRL) − Total Investido` |
| `Lucro corrigido` | formula: `Valor atual (BRL) − Total corrigido` |

Atencao: `Total Investido` (BRL) e `Total investido` (USD) diferem so por uma
maiuscula e sao moedas diferentes. Vale renomear para `Total descontado (BRL)` e
`Total investido (USD)` quando der.

Essas propriedades vivem na database `Investimentos` (onde a pagina ESPP e uma
linha) — no Notion nao existe propriedade de uma pagina so. Na pratica nao
incomoda: a view da pagina Financas mostra so o nome, e em `Ações`/`Renda fixa`
os campos ficam vazios, agrupados em "propriedades vazias".

O rollup so enxerga o que estiver ligado pela relacao `Lançamentos`, entao a
plataforma reescreve essa relacao a cada execucao: linha nova entra sozinha,
linha apagada sai.

## Casas decimais

Padrao financeiro, aplicado nas formulas do Notion e no codigo:

- dinheiro (valores, lucro, precos): **2 casas**
- cambio: **4 casas**
- acoes compradas: **5 casas**
- `Valor investido (USD)`: 4 casas, porque dividendo reinvestido tem centavo
  quebrado e 2 casas distorceriam a fracao de acao comprada

## Setup

### 1. Integracao do Notion

1. Crie uma integracao interna em <https://www.notion.so/profile/integrations>
   (capabilities: ler e atualizar conteudo).
2. Copie o token (`ntn_...`).
3. Na pagina **Finanças**: menu `...` (canto superior direito) > `Conexoes` >
   adicione a integracao. Sem isso a API responde 404 mesmo com token valido.

   Tem que ser na `Finanças` mesmo, nao na tabela de lancamentos: o script
   escreve em dois niveis da arvore — nos lancamentos e na pagina ESPP (que e
   uma linha da database `Investimentos`, dentro de um callout da `Finanças`).
   Conectando na `Finanças`, tudo abaixo herda o acesso.

### 2. Local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest

cp .env.example .env    # preencha NOTION_TOKEN

pytest -q                     # 63 testes, sem rede
python -m portfolio --dry-run # calcula e imprime, sem gravar nada
python -m portfolio           # grava no Notion
```

O `--dry-run` imprime, por plataforma, a tabela do jeito que o Notion deveria
estar exibindo (com totais), marcando com `*` as linhas que seriam gravadas.

### 3. GitHub Actions

Em `Settings > Secrets and variables > Actions`, crie:

- `NOTION_TOKEN`
- `ESPP_DATABASE_ID` (= `c5a0e7612c284375842ab812d61d3f75`)
- `ESPP_PAGE_ID` (= `3ce30ca2d8ff80a2a360c5461ca6afc8`)

O workflow `.github/workflows/update-espp.yml` roda `0 13,17,21 * * 1-5` UTC
(10h/14h/18h BRT, dias uteis) e tambem manualmente por `workflow_dispatch`,
onde da para marcar `dry_run` para so conferir sem gravar.

## Sobre `calculos.py`

Ele repete em Python as formulas que rodam no Notion. Serve para o relatorio do
`--dry-run` e para os testes conferirem a matematica contra as 9 linhas reais da
planilha antiga. **Se mudar uma formula no Notion, mude ali tambem** — senao o
relatorio passa a mentir.

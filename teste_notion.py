from notion_client import Client
import json
# Inicialize o client com seu token de integração
notion = Client(auth="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")

# ID do database que contém os cards (você encontra na URL do seu database)
database_id = "18f30ca2d8ff81ef947bf436db931bf2"

# 1. Consulta o database e recupera os cards
response = notion.databases.query(database_id=database_id)
pages = response.get("results", [])

if not pages:
    print("Nenhum card encontrado no database.")
    exit()

# Seleciona o primeiro card para o exemplo
first_card = pages[0]
props = first_card["properties"]

# 2. Extrai os valores necessários das propriedades
# (Certifique-se de que os nomes abaixo batem exatamente com os do seu database.)
preco_compra = props.get("Preço de compra", {}).get("number")
quantidade = props.get("Quantidade", {}).get("number")
valor_atual = props.get("Valor Atual", {}).get("number")

print("Valores extraídos:")
print(f"Preço de Compra: {preco_compra}")
print(f"Quantidade: {quantidade}")
print(f"Valor Atual: {valor_atual}")

# Verifica se os valores necessários estão definidos
if preco_compra is None or quantidade is None or valor_atual is None:
    print("Alguma das propriedades numéricas não está definida. Verifique seu database.")
    exit()

# 3. Realiza os cálculos
rendimento = (valor_atual - preco_compra) * quantidade


print("\nCálculos realizados:")
print(f"Rendimento: {rendimento}")


# 4. Prepara o payload de atualização
# Certifique-se de que as propriedades "total compra", "Rendimento" e "Rendimento atual"
# são do tipo number (não fórmula) para que possam ser atualizadas.
update_payload = {
    "Rendimento": {"number": rendimento},
}

# Atualiza o card com os novos valores
updated_page = notion.pages.update(
    page_id=first_card["id"],
    properties=update_payload
)

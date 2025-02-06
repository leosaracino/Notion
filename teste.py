import math
import datetime
import holidays

def truncar(valor, casas):
    """
    Trunca o número 'valor' para 'casas' decimais.
    """
    fator = 10 ** casas
    return math.floor(valor * fator) / fator

def gerar_dias_uteis(data_inicio, data_fim):
    """
    Gera uma lista de dias úteis (excluindo finais de semana e feriados) entre
    data_inicio e data_fim.
    """
    # Cria o calendário de feriados para o Brasil (para o(s) ano(s) envolvidos)
    anos = list({data_inicio.year, data_fim.year})
    feriados = holidays.Brazil(years=anos)
    
    # Adiciona feriados que não são nacionais, se necessário (ex.: Carnaval, Corpus Christi)
    # Para exemplo, adicionamos datas fictícias:
    feriados.update({
        datetime.date(2025, 3, 3): "Carnaval",
        datetime.date(2025, 3, 4): "Carnaval",
        datetime.date(2025, 6, 19): "Corpus Christi"
    })
    
    dias_uteis = []
    dia = data_inicio
    while dia <= data_fim:
        if dia.weekday() < 5 and dia not in feriados:  # weekday() 0=segunda ... 6=domingo
            dias_uteis.append(dia)
        dia += datetime.timedelta(days=1)
    return dias_uteis

def calcular_rendimento(
    valor_aplicado,   # valor investido (B1)
    rendimento,       # rendimento ex: 1.15 para 115% (I1)
    cdi_anual,        # taxa anual do CDI, ex: 13.65
    data_inicio,      # data de início do investimento
    data_final        # data final (hoje)
):
    D1 = 1000  # Valor base fixo
    # Célula E1: razão do valor aplicado pelo valor base
    razao_aplicado = valor_aplicado / D1

    # Calcula a taxa diária a partir do CDI anual
    # Fórmula: ((((cdi/100)+1)^(1/252))-1), arredondada para 8 casas.
    taxa_diaria = round(((1 + cdi_anual/100) ** (1/252)) - 1, 8)
    
    # Obter lista de dias úteis
    dias_uteis = gerar_dias_uteis(data_inicio, data_final)
    
    # Listas para armazenar os cálculos diários (opcional, para debug)
    lista_taxa_diaria = []
    lista_fator_diario = []
    lista_acumulado = []
    lista_valor_diario = []
    
    # Coluna F: acumulado, F3 = 1
    acumulado = 1.0
    
    # Para cada dia útil, calcula:
    for idx, dia in enumerate(dias_uteis, start=1):
        # Coluna D: taxa diária (já calculada acima para cada dia)
        D = taxa_diaria
        lista_taxa_diaria.append(D)
        
        # Coluna E: fator diário = trunc(1 + (D * rendimento), 15)
        fator_diario = truncar(1 + (D * rendimento), 15)
        lista_fator_diario.append(fator_diario)
        
        # Atualiza o acumulado: produto dos fatores diários
        # Em Excel: acumulado = ARRED(TRUNCAR(PRODUTO( fatores_diarios ) ,16),8)
        acumulado *= fator_diario
        acumulado_trunc = truncar(acumulado, 16)
        acumulado = round(acumulado_trunc, 8)
        lista_acumulado.append(acumulado)
        
        # Coluna G: valor diário = trunc(acumulado, 8) * 1000
        valor_diario = truncar(acumulado, 8) * D1
        lista_valor_diario.append(valor_diario)
    
    # Para o dia final (hoje) usamos o acumulado encontrado
    # Fórmula do valor bruto: =E1*(ARRED(acumulado,4))
    acumulado_final_arred = round(acumulado, 4)
    valor_bruto = razao_aplicado * acumulado_final_arred

    # Calcula número de dias corridos do investimento
    dias_investidos = (data_final - data_inicio).days

    # Define alíquota do IR conforme os dias investidos
    if dias_investidos <= 180:
        aliquota = 0.225
    elif dias_investidos <= 360:
        aliquota = 0.20
    elif dias_investidos <= 720:
        aliquota = 0.175
    else:
        aliquota = 0.15

    # Cálculo do IR: (valor bruto - valor aplicado)*aliquota
    valor_ir = (valor_bruto - valor_aplicado) * aliquota

    # Valor líquido: valor bruto - IR
    valor_liquido = valor_bruto - valor_ir

    # Retorna os resultados e também alguns detalhes se necessário
    return {
        "valor_aplicado": valor_aplicado,
        "D1": D1,
        "razao_aplicado": razao_aplicado,
        "taxa_diaria": taxa_diaria,
        "dias_investidos": dias_investidos,
        "acumulado_final": acumulado,
        "acumulado_final_arred": acumulado_final_arred,
        "valor_bruto": valor_bruto,
        "aliquota_ir": aliquota,
        "valor_ir": valor_ir,
        "valor_liquido": valor_liquido,
        "lista_dias": dias_uteis,
        "lista_acumulado": lista_acumulado
    }

# Exemplo de uso:
if __name__ == "__main__":
    # Parâmetros de entrada
    valor_aplicado = 5000.00       # Exemplo: R$ 5.000,00
    rendimento = 1.15              # Exemplo: 115% (1.15)
    cdi_anual = 13.65              # Exemplo: 13,65% ao ano
    
    # Datas de início e fim do investimento
    data_inicio = datetime.date(2025, 1, 2)   # supondo que o investimento começou em 02/01/2025
    data_final = datetime.date.today()        # ou especifique uma data final desejada

    resultado = calcular_rendimento(valor_aplicado, rendimento, cdi_anual, data_inicio, data_final)

    print("Resumo do Investimento:")
    print(f"Valor Aplicado: R$ {resultado['valor_aplicado']:.2f}")
    print(f"Dias Investidos: {resultado['dias_investidos']} dias")
    print(f"Acumulado Final (F): {resultado['acumulado_final']}")
    print(f"Valor Bruto: R$ {resultado['valor_bruto']:.4f}")
    print(f"Alíquota IR: {resultado['aliquota_ir']*100:.1f}%")
    print(f"Valor IR: R$ {resultado['valor_ir']:.4f}")
    print(f"Valor Líquido: R$ {resultado['valor_liquido']:.4f}")

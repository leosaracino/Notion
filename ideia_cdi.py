import math

def truncar_excel(d3, i1, casas_decimais=15):
    """
    Replica a função do Excel: =TRUNCAR(1+(D3*$I$1);15)
    
    Parâmetros:
        d3             - valor correspondente à célula D3
        i1             - valor correspondente à célula I1
        casas_decimais - número de casas decimais para truncar (padrão é 15)
        
    Retorna:
      O resultado de 1 + (d3 * i1) truncado para 'casas_decimais' casas decimais.
    """
    # Calcula a expressão: 1 + (D3 * I1)
    valor = 1 + ((d3/100) * i1)
    
    # Calcula o fator de multiplicação para preservar as casas decimais
    fator = 10 ** casas_decimais
    
    # Utiliza math.trunc para remover os dígitos extras
    valor_truncado = math.trunc(valor * fator) / fator
    return valor_truncado

# Exemplo de uso:
resultado = truncar_excel(2.3456789, 3.1415926)
print(resultado)

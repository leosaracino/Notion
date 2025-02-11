import requests
import datetime
import holidays
from decimal import Decimal, getcontext, ROUND_HALF_UP, ROUND_DOWN

# Configurar o contexto para arredondamento
getcontext().rounding = ROUND_HALF_UP

def truncate_decimal(number, decimals):
    return number.quantize(Decimal(f'1e-{decimals}'), rounding=ROUND_DOWN)

def generate_business_days(start_date, end_date):
    br_holidays = holidays.Brazil(years=range(start_date.year, end_date.year + 1))
    manual_holidays = {
        # Exemplo para 2025
        datetime.date(2025, 3, 3): "Carnaval",
        datetime.date(2025, 3, 4): "Carnaval",
        datetime.date(2025, 6, 19): "Corpus Christi",
        # Exemplo para 2026
        datetime.date(2026, 2, 16): "Carnaval",
        datetime.date(2026, 2, 17): "Carnaval",
        datetime.date(2026, 6, 4): "Corpus Christi",
    }
    br_holidays.update(manual_holidays)
    
    business_days = []
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5 and current_date not in br_holidays:
            business_days.append(current_date)
        current_date += datetime.timedelta(days=1)
    return business_days

def fetch_cdi_rates(start_date, end_date):
    start_str = start_date.strftime('%d/%m/%Y')
    end_str = end_date.strftime('%d/%m/%Y')
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados?formato=json&dataInicial={start_str}&dataFinal={end_str}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        cdi_rates = {}
        for item in data:
            date = datetime.datetime.strptime(item['data'], '%d/%m/%Y').date()
            cdi_rates[date] = Decimal(item['valor'])
        return cdi_rates
    except Exception as e:
        print(f"Erro ao buscar taxas CDI: {e}")
        return {}

def calculate_rendimento_fixo(applied_value, rendimento_percent, start_date, end_date):
    applied_value = Decimal(applied_value)
    rendimento_percent = Decimal(rendimento_percent)
    
    business_days = generate_business_days(start_date, end_date)
    if not business_days:
        raise ValueError("Não há dias úteis no período especificado.")
    
    cdi_rates = fetch_cdi_rates(business_days[0], business_days[-1])
    missing_dates = [date for date in business_days if date not in cdi_rates]
    if missing_dates:
        raise ValueError(f"Taxas CDI ausentes para as datas: {missing_dates}")
    
    e_values = []
    for date in business_days:
        cdi = cdi_rates[date]
        daily_rate = ((cdi / Decimal('100') + Decimal('1')) ** (Decimal('1')/Decimal('252'))) - Decimal('1')
        daily_rate_rounded = daily_rate.quantize(Decimal('1e-8'), rounding=ROUND_HALF_UP)
        e = Decimal('1') + (daily_rate_rounded * (rendimento_percent / Decimal('100')))
        e_truncated = truncate_decimal(e, 15)
        e_values.append(e_truncated)
    
    accumulated_product = [Decimal('1')]
    for e in e_values:
        product = accumulated_product[-1] * e
        product_truncated = truncate_decimal(product, 16)
        product_rounded = product_truncated.quantize(Decimal('1e-8'), rounding=ROUND_HALF_UP)
        accumulated_product.append(product_rounded)
    
    g_values = [truncate_decimal(accumulated_product[i+1] * Decimal('1000'), 8) for i in range(len(business_days))]
    
    e1 = applied_value / Decimal('1000')
    g_last = g_values[-1]
    gross_value = e1 * g_last
    gross_value_rounded = gross_value.quantize(Decimal('1e-4'), rounding=ROUND_HALF_UP)
    
    days = len(business_days)
    if days <= 180:
        tax_rate = Decimal('0.225')
    elif days <= 360:
        tax_rate = Decimal('0.20')
    elif days <= 720:
        tax_rate = Decimal('0.175')
    else:
        tax_rate = Decimal('0.15')
    
    ir = (gross_value_rounded - applied_value) * tax_rate
    ir = max(ir, Decimal('0')).quantize(Decimal('1e-4'), rounding=ROUND_HALF_UP)
    net_value = gross_value_rounded - ir
    
    return {
        'gross_value': float(gross_value_rounded),
        'ir': float(ir),
        'net_value': float(net_value),
    }

# Exemplo de uso
if __name__ == "__main__":
    resultado = calculate_rendimento_fixo(
        applied_value='10000',
        rendimento_percent='115',
        start_date=datetime.date(2025, 1, 2),
        end_date=datetime.date(2025, 12, 31)
    )
    print("Valor Bruto:", resultado['gross_value'])
    print("IR:", resultado['ir'])
    print("Valor Líquido:", resultado['net_value'])
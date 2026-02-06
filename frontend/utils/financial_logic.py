import pandas as pd
import numpy as np
import numpy_financial as npf

def calculate_debt_schedule(monto, tasa_anual, plazo_anos):
    """Calcula la tabla de amortización (Intereses) para una deuda específica."""
    if monto <= 0 or plazo_anos <= 0:
        return np.zeros(120) # Retorna ceros para 10 años por seguridad
    
    tasa_mensual = (tasa_anual / 100) / 12
    n_periodos = int(plazo_anos * 12)
    
    try:
        cuota = npf.pmt(tasa_mensual, n_periodos, -monto)
    except:
        cuota = 0
    
    intereses = []
    saldo = monto
    
    # Generamos proyección hasta 120 meses (10 años)
    for _ in range(120): 
        if saldo <= 0.01:
            intereses.append(0)
            continue
            
        interes = saldo * tasa_mensual
        amort = cuota - interes
        if saldo - amort < 0: amort = saldo
            
        intereses.append(interes)
        saldo -= amort
        
    return np.array(intereses)

def run_financial_model(
    plazo_anos, 
    fiu_perf_start, fiu_npa_start, 
    new_debt_amount, new_debt_rate, new_debt_type,
    rev_rate, cof_rate, provision_rate, rec_npa_rate, opex_pct, tax_rate,
    cogs_amount, dep_amort_amount, fx_impact, non_op_result,
    df_current_debt
):
    total_meses = int(plazo_anos * 12)
    # Rango de fechas mensual
    rng = pd.date_range(start=pd.Timestamp.now().normalize(), periods=total_meses, freq='ME')
    
    # Tasas mensuales
    r_rev = rev_rate / 100 / 12
    r_cof = cof_rate / 100 / 12
    r_prov = provision_rate / 100 / 12
    r_rec = (1 - (1 - rec_npa_rate/100)**(1/12))
    
    # --- 1. PROCESAR DEUDA ACTUAL (TABLA EDITABLE) ---
    total_int_actual = np.zeros(total_meses)
    
    if not df_current_debt.empty:
        for _, row in df_current_debt.iterrows():
            try:
                m = float(row.get('USD Balance Equiv', 0))
                t = float(row.get('Weighted average annual rate', 0))
                p = float(row.get('Plazo Restante (Años)', 3)) 
                
                # Calcular vector de intereses
                ints = calculate_debt_schedule(m, t, p)
                
                # Sumar al vector total (recortando o rellenando)
                len_fill = min(len(ints), total_meses)
                total_int_actual[:len_fill] += ints[:len_fill]
            except: continue

    # --- 2. SIMULACIÓN MENSUAL ---
    fiu_perf = fiu_perf_start
    fiu_npa = fiu_npa_start
    saldo_new_debt = new_debt_amount
    r_new_debt = (new_debt_rate/100)/12
    
    cuota_new = 0
    if new_debt_amount > 0 and new_debt_type == 'Amortizado':
        cuota_new = npf.pmt(r_new_debt, total_meses, -new_debt_amount)

    results = []
    
    for i in range(total_meses):
        # Drivers Operativos
        revenue = fiu_perf * r_rev
        cof = fiu_perf * r_cof
        prov = (fiu_perf + fiu_npa) * r_prov
        cogs = cogs_amount / 12 
        
        gross_income = revenue - prov - cof - cogs
        opex = revenue * (opex_pct / 100)
        ebitda = gross_income - opex
        
        # Items bajo EBITDA
        dep_amort = dep_amort_amount / 12
        fx = fx_impact / 12
        non_op = non_op_result / 12
        
        # Intereses (Actual + Nueva)
        int_new = saldo_new_debt * r_new_debt
        int_total = int_new + (total_int_actual[i] if i < len(total_int_actual) else 0)
        
        ebt = ebitda - dep_amort + fx + non_op - int_total
        tax = max(0, ebt * (tax_rate/100))
        net_income = ebt - tax
        
        # Movimiento de Capital (Deuda Nueva)
        amort_new = 0
        if new_debt_amount > 0:
            if new_debt_type == 'Amortizado': amort_new = cuota_new - int_new
            elif new_debt_type == 'Bullet' and i == total_meses - 1: amort_new = saldo_new_debt
        
        # Evolución FIU (Simplificada)
        recup = fiu_npa * r_rec
        fiu_npa -= recup
        # Asumimos reinversión del flujo neto
        cash_flow = net_income + dep_amort + recup - amort_new
        fiu_perf += cash_flow
        saldo_new_debt -= amort_new
        
        results.append({
            'FIU Performing': fiu_perf,
            'FIU NPA': fiu_npa,
            'Revenues': revenue,
            'Provisions': -prov,
            'COF': -cof,
            'COGS': -cogs,
            'Gross Income': gross_income,
            'OPEX': -opex,
            'EBITDA': ebitda,
            'Dep & Amort': -dep_amort,
            'Exchange Rates': fx,
            'Non Operating': non_op,
            'Financial Expenses': -int_total,
            'EBT': ebt,
            'Taxes': -tax,
            'Earnings': net_income
        })

    df_res = pd.DataFrame(results, index=rng)
    
    # Generar versión Anual
    df_yr = df_res.resample('YE').sum()
    # Corregir Saldos (no se suman, se toma el último)
    df_yr['FIU Performing'] = df_res['FIU Performing'].resample('YE').last()
    df_yr['FIU NPA'] = df_res['FIU NPA'].resample('YE').last()
    
    return df_res, df_yr

def format_pnl_display(df_input, period_type='Anual'):
    """
    Transforma el DataFrame (mensual o anual) al formato P&L vertical solicitado.
    """
    # Formato de columnas (Fechas)
    if period_type == 'Mensual':
        columns = df_input.index.strftime('%b-%y')
        df_iter = df_input.copy()
        df_iter.index = columns
    else:
        columns = df_input.index.year
        df_iter = df_input.copy()
        df_iter.index = columns

    data_dict = {}

    def calc_margin(num, den):
        return (num / den * 100) if den != 0 else 0

    # Construcción de filas
    for col_name in df_iter.index:
        row = df_iter.loc[col_name]
        rev = row['Revenues']
        
        col_data = {
            'FIU Performing': row['FIU Performing'],
            'FIU NPA': row['FIU NPA'],
            'Total FIU': row['FIU Performing'] + row['FIU NPA'],
            ' ': np.nan, # Separador
            'Revenues': rev,
            'Provisions & Writes off': row['Provisions'],
            'COF': row['COF'],
            'COGS': row['COGS'],
            'Gross Income': row['Gross Income'],
            'OPEX': row['OPEX'],
            'Op. Income / EBITDA': row['EBITDA'],
            '  ': np.nan, # Separador
            'Depreciation & Amortization': row['Dep & Amort'],
            'Exchange rates': row['Exchange Rates'],
            'Non operating rev/expenses': row['Non Operating'],
            'Financial Expenses': row['Financial Expenses'],
            'Earnings before tax (EBT)': row['EBT'],
            'Taxes': row['Taxes'],
            'Earnings (Net Income)': row['Earnings'],
            '   ': np.nan, # Separador Inferior
            'Gross Margin %': calc_margin(row['Gross Income'], rev),
            'Operating Margin %': calc_margin(row['EBITDA'], rev),
            'Net Margin %': calc_margin(row['Earnings'], rev)
        }
        data_dict[col_name] = col_data
        
    return pd.DataFrame(data_dict)
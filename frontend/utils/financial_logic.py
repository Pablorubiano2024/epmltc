import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.graph_objs as go

# --- CONFIGURACIÓN DE COLORES ---
PRIMARY = "#122442"
SECONDARY = "#19AC86"
ACCENT = "#FE4A49"
WHITE = "#FFFFFF"
DARK = "#232323"
LIGHT_BLUE = "#A2E3EB"

def run_financial_model(plazo, fiu_perf_inicial, fiu_npa_inicial, monto_deuda, interes_prestamo, loan_type, revenue_rate, cof_rate, provision_rate, rec_npa, opex_pct, tax_rate):
    revenue_rate_mensual = revenue_rate / 100 / 12
    cof_rate_mensual = cof_rate / 100 / 12
    provision_rate_mensual = provision_rate / 100 / 12
    interes_prestamo_mensual = (interes_prestamo / 100) / 12
    rec_npa_mensual = (1 - (1 - rec_npa / 100)**(1/12)) if rec_npa < 100 else 1.0
    opex_pct_dec = opex_pct / 100
    tax_rate_dec = tax_rate / 100
    
    total_meses = int(plazo * 12)
    start_date = pd.to_datetime('today').to_period('M').start_time
    meses_idx = pd.date_range(start=start_date, periods=total_meses, freq='ME') # ME = Month End (pandas nuevo)
    df = pd.DataFrame(index=meses_idx)

    cols = ['fiu_performing_inicio', 'fiu_npa_inicio', 'ingresos', 'cof', 'provisiones', 'utilidad_bruta', 'opex', 'ebitda', 'interes_prestamo', 'amortizacion_prestamo', 'recuperacion_npa', 'ebt', 'impuestos', 'utilidad_neta', 'flujo_caja_equity', 'fiu_performing_fin']
    for col in cols: df[col] = 0.0
    
    saldo_prestamo_actual = monto_deuda
    fiu_perf_actual = fiu_perf_inicial
    fiu_npa_actual = fiu_npa_inicial
    cuota_mensual = 0
    
    if loan_type == 'Amortizado' and monto_deuda > 0 and total_meses > 0:
        if interes_prestamo_mensual > 0:
            cuota_mensual = npf.pmt(interes_prestamo_mensual, total_meses, -monto_deuda)
        else:
            cuota_mensual = monto_deuda / total_meses

    for i, mes_actual in enumerate(df.index):
        df.loc[mes_actual, 'fiu_performing_inicio'] = fiu_perf_actual
        df.loc[mes_actual, 'fiu_npa_inicio'] = fiu_npa_actual
        
        ingresos_mes = fiu_perf_actual * revenue_rate_mensual
        cof_mes = fiu_perf_actual * cof_rate_mensual
        provisiones_mes = (fiu_perf_actual + fiu_npa_actual) * provision_rate_mensual
        utilidad_bruta_mes = ingresos_mes - cof_mes - provisiones_mes
        opex_mes = ingresos_mes * opex_pct_dec
        ebitda_mes = utilidad_bruta_mes - opex_mes
        interes_mes = saldo_prestamo_actual * interes_prestamo_mensual
        ebt_mes = ebitda_mes - interes_mes
        impuestos_mes = max(0, ebt_mes * tax_rate_dec)
        utilidad_neta_mes = ebt_mes - impuestos_mes
        recuperacion_npa_mes = fiu_npa_actual * rec_npa_mensual

        amortizacion_mes = 0
        if saldo_prestamo_actual > 0.001:
            if loan_type == 'Bullet':
                if i == total_meses - 1: amortizacion_mes = saldo_prestamo_actual
            else:
                pago_principal = cuota_mensual - interes_mes
                amortizacion_mes = min(saldo_prestamo_actual, max(0, pago_principal))
        
        caja_generada_operacion = ebitda_mes - impuestos_mes
        caja_total_disponible = caja_generada_operacion + recuperacion_npa_mes
        flujo_caja_libre_equity = caja_total_disponible - interes_mes - amortizacion_mes
        
        df.loc[mes_actual, ['ingresos', 'cof', 'provisiones', 'utilidad_bruta', 'opex', 'ebitda', 'interes_prestamo', 'amortizacion_prestamo', 'recuperacion_npa', 'ebt', 'impuestos', 'utilidad_neta', 'flujo_caja_equity']] = \
            [ingresos_mes, cof_mes, provisiones_mes, utilidad_bruta_mes, opex_mes, ebitda_mes, interes_mes, amortizacion_mes, recuperacion_npa_mes, ebt_mes, impuestos_mes, utilidad_neta_mes, flujo_caja_libre_equity]
        
        saldo_prestamo_actual -= amortizacion_mes
        fiu_perf_actual += flujo_caja_libre_equity
        fiu_npa_actual *= (1 - rec_npa_mensual)
        
        df.loc[mes_actual, 'fiu_performing_fin'] = fiu_perf_actual
    
    df['saldo_prestamo'] = monto_deuda - df['amortizacion_prestamo'].cumsum()
    df['saldo_prestamo'] = df['saldo_prestamo'].clip(lower=0)
    
    df_anual = df.resample('YE').sum() # 'YE' para pandas moderno, 'A' para antiguos
    df_anual['Año'] = df_anual.index.year
    df_anual['saldo_prestamo'] = df['saldo_prestamo'].resample('YE').last().round(2)
    df_anual['fiu_performing_fin'] = df['fiu_performing_fin'].resample('YE').last()
    df_anual['fiu_npa_fin'] = df['fiu_npa_inicio'].resample('YE').last() * (1-rec_npa_mensual)
    
    return df, df_anual

def calculate_kpis(df_anual, monto_equity, plazo, df_saldo_prestamo_mensual):
    utilidad_neta_total = df_anual['utilidad_neta'].sum()
    roi = (utilidad_neta_total / monto_equity) * 100 if monto_equity > 0 else float('inf')
    
    mes_pago_final = df_saldo_prestamo_mensual[df_saldo_prestamo_mensual < 0.01].first_valid_index()
    if mes_pago_final:
        start_date = df_saldo_prestamo_mensual.index[0]
        meses_payback = (mes_pago_final.year - start_date.year) * 12 + (mes_pago_final.month - start_date.month) + 1
        payback_text = f"{meses_payback / 12:.1f} Años"
    else:
        payback_text = f">{plazo} Años"
        
    return {
        'roi': roi, 
        'roi_text': f"{roi:.1f}%", 
        'profit_text': f"${utilidad_neta_total:,.2f}",
        'payback_text': payback_text
    }

def create_figures(df_anual, monto_deuda):
    hover_template = "<b>%{y:,.2f} MUSD</b><extra></extra>"
    text_template = "%{y:,.2f}"
    
    # 1. Cartera
    fig_cartera = go.Figure(layout=dict(title="Evolución de Cartera (FIU a fin de año)", barmode='stack', yaxis_title="MUSD"))
    fig_cartera.add_trace(go.Bar(x=df_anual['Año'], y=df_anual['fiu_performing_fin'], name='FIU Performing', marker_color=PRIMARY))
    fig_cartera.add_trace(go.Bar(x=df_anual['Año'], y=df_anual['fiu_npa_fin'], name='FIU NPA', marker_color=ACCENT))
    
    # 2. P&L
    fig_pnl = go.Figure(layout=dict(title="Evolución del P&L Anual", barmode='group', yaxis_title="MUSD"))
    fig_pnl.add_trace(go.Bar(x=df_anual['Año'], y=df_anual['ingresos'], name='Ingresos', marker_color=SECONDARY))
    fig_pnl.add_trace(go.Bar(x=df_anual['Año'], y=df_anual['ebitda'], name='EBITDA', marker_color=LIGHT_BLUE))
    fig_pnl.add_trace(go.Bar(x=df_anual['Año'], y=df_anual['utilidad_neta'], name='Utilidad Neta', marker_color=PRIMARY))

    # 3. Flujo de Caja
    fig_flujo = go.Figure(layout=dict(title="Fuentes y Usos de Caja Anual", barmode='relative', yaxis_title="MUSD"))
    fig_flujo.add_trace(go.Bar(x=df_anual['Año'], y=df_anual['ebitda'] - df_anual['impuestos'], name='Caja de Operación', marker_color=SECONDARY))
    fig_flujo.add_trace(go.Bar(x=df_anual['Año'], y=-(df_anual['amortizacion_prestamo'] + df_anual['interes_prestamo']), name='Servicio de Deuda', marker_color=ACCENT))
    fig_flujo.add_trace(go.Scatter(x=df_anual['Año'], y=df_anual['flujo_caja_equity'], name='Flujo Reinversión (FCFE)', mode='lines+markers', line=dict(color=PRIMARY, width=3)))

    # 4. Deuda
    fig_loan = go.Figure(layout=dict(title="Plan de Pagos de Deuda", barmode='stack'))
    fig_loan.add_trace(go.Bar(x=df_anual['Año'], y=df_anual['amortizacion_prestamo'], name='Amortización', marker_color=PRIMARY))
    fig_loan.add_trace(go.Bar(x=df_anual['Año'], y=df_anual['interes_prestamo'], name='Intereses', marker_color=ACCENT))
    fig_loan.add_trace(go.Scatter(x=df_anual['Año'], y=df_anual['saldo_prestamo'], name='Saldo Deuda', mode='lines+markers', line=dict(color=SECONDARY, width=3), yaxis="y2"))
    fig_loan.update_layout(yaxis=dict(title='Pago Anual'), yaxis2=dict(title='Saldo', overlaying='y', side='right', showgrid=False, range=[0, max(1, monto_deuda * 1.1)]))

    return {'cartera': fig_cartera, 'pnl': fig_pnl, 'flujo': fig_flujo, 'loan': fig_loan}
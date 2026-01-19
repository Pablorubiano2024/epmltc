import sys
import os

# ==============================================================================
# 0. FIX DE IMPORTACIÓN (SOLUCIÓN AL ERROR)
# ==============================================================================
# Obtenemos la ruta absoluta de este archivo y subimos 3 niveles para llegar a la raíz 'epmltc'
# Estructura: epmltc -> frontend -> pages -> este_archivo.py
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(frontend_dir)
sys.path.append(root_dir)

# ==============================================================================
# IMPORTS
# ==============================================================================
import streamlit as st
import pandas as pd
# Ahora sí encontrará este módulo sin problemas
from frontend.utils.financial_logic import run_financial_model, calculate_kpis, create_figures

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA
# ==============================================================================
st.set_page_config(page_title="Proyección Financiera", layout="wide", page_icon="📈")

st.title("📈 Modelo Financiero: Compra de Cartera")
st.markdown("Simulación de rentabilidad, flujo de caja y amortización de deuda.")

# --- INICIALIZAR ESTADO (CARTERA POR DEFECTO) ---
if 'portfolio_data' not in st.session_state:
    st.session_state.portfolio_data = pd.DataFrame([
        {'País': 'Chile', 'FIU Performing': 86.17, 'FIU NPA': 21.28},
        {'País': 'Perú', 'FIU Performing': 30.67, 'FIU NPA': 21.95},
        {'País': 'Colombia', 'FIU Performing': 97.25, 'FIU NPA': 9.63},
        {'País': 'Brasil', 'FIU Performing': 9.32, 'FIU NPA': 18.44},
    ])

# ==============================================================================
# 1. BARRA LATERAL (INPUTS)
# ==============================================================================
st.sidebar.header("Parámetros del Modelo")

with st.sidebar.expander("💰 Financiamiento", expanded=True):
    monto_deuda = st.number_input("Monto Deuda (MUSD)", value=100.0, step=1.0)
    monto_equity = st.number_input("Aporte Equity (MUSD)", value=80.0, step=1.0)
    tasa_interes = st.number_input("Tasa Interés Anual (%)", value=10.0, step=0.1)
    plazo_anos = st.number_input("Plazo (Años)", value=5, min_value=1, max_value=30)
    tipo_amortizacion = st.radio("Tipo Amortización", ["Amortizado", "Bullet"])
    
    st.info(f"Inversión Total: ${monto_deuda + monto_equity:,.2f} MUSD")

with st.sidebar.expander("⚙️ Operativos", expanded=False):
    revenue_rate = st.number_input("Ingresos / FIU (%)", value=24.0, step=0.1)
    cof_rate = st.number_input("COF / FIU (%)", value=8.6, step=0.1)
    provision_rate = st.number_input("Provisiones / FIU Total (%)", value=2.1, step=0.1)
    recupera_npa = st.number_input("Recuperación NPA Anual (%)", value=10.0, step=1.0)
    opex_pct = st.number_input("OPEX (% de Ingresos)", value=44.0, step=1.0)
    tax_rate = st.number_input("Impuestos (% sobre EBT)", value=27.0, step=1.0)

# ==============================================================================
# 2. GESTIÓN DE CARTERA (EDITABLE)
# ==============================================================================
st.subheader("1. Configuración de Cartera Inicial")
col_table, col_filter = st.columns([2, 1])

with col_table:
    st.markdown("Edita los valores de FIU por país:")
    # Data Editor permite editar la tabla como un Excel directamente en la web
    edited_portfolio = st.data_editor(
        st.session_state.portfolio_data,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "FIU Performing": st.column_config.NumberColumn(format="$%.2f"),
            "FIU NPA": st.column_config.NumberColumn(format="$%.2f")
        }
    )
    # Actualizar estado si cambia
    st.session_state.portfolio_data = edited_portfolio

with col_filter:
    st.markdown("### Filtro de Vista")
    paises_disponibles = ["Regional (Todos)"] + edited_portfolio['País'].tolist()
    filtro_pais = st.selectbox("Analizar Proyección Para:", paises_disponibles)
    
    # Calcular totales según filtro para pasar al modelo
    if filtro_pais == "Regional (Todos)":
        fiu_perf = edited_portfolio['FIU Performing'].sum()
        fiu_npa = edited_portfolio['FIU NPA'].sum()
        # Asignación de deuda/equity total
        deuda_calc = monto_deuda
        equity_calc = monto_equity
    else:
        # Filtrar solo el país seleccionado
        row = edited_portfolio[edited_portfolio['País'] == filtro_pais].iloc[0]
        fiu_perf = row['FIU Performing']
        fiu_npa = row['FIU NPA']
        
        # Calcular peso para asignar deuda/equity proporcionalmente
        total_global = edited_portfolio['FIU Performing'].sum() + edited_portfolio['FIU NPA'].sum()
        total_local = fiu_perf + fiu_npa
        peso = total_local / total_global if total_global > 0 else 0
        
        deuda_calc = monto_deuda * peso
        equity_calc = monto_equity * peso
        
        st.caption(f"Peso del país en el portafolio: {peso:.1%}")
        st.caption(f"Deuda Asignada: ${deuda_calc:,.2f} | Equity Asignado: ${equity_calc:,.2f}")

# ==============================================================================
# 3. EJECUCIÓN DEL MODELO
# ==============================================================================

if st.button("🚀 Generar Proyección", type="primary"):
    
    # Llamamos a la lógica matemática (importada de utils)
    df_mensual, df_anual = run_financial_model(
        plazo_anos, fiu_perf, fiu_npa, deuda_calc, tasa_interes, tipo_amortizacion,
        revenue_rate, cof_rate, provision_rate, recupera_npa, opex_pct, tax_rate
    )
    
    # Calcular KPIs
    kpis = calculate_kpis(df_anual, equity_calc, plazo_anos, df_mensual['saldo_prestamo'])
    figs = create_figures(df_anual, deuda_calc)
    
    # --- RESULTADOS VISUALES ---
    st.divider()
    st.subheader(f"Resultados: {filtro_pais}")
    
    # KPIs
    k1, k2, k3 = st.columns(3)
    k1.metric("ROI s/ Equity", kpis['roi_text'], help="Retorno sobre el capital invertido")
    k2.metric("Utilidad Neta Total", kpis['profit_text'], help="Suma de utilidades del periodo")
    k3.metric("Payback Deuda", kpis['payback_text'], help="Tiempo para pagar la deuda total")
    
    # Gráficos Fila 1
    g1, g2 = st.columns(2)
    g1.plotly_chart(figs['cartera'], use_container_width=True)
    g2.plotly_chart(figs['pnl'], use_container_width=True)
    
    # Gráficos Fila 2
    g3, g4 = st.columns(2)
    g3.plotly_chart(figs['flujo'], use_container_width=True)
    g4.plotly_chart(figs['loan'], use_container_width=True)
    
    # Tabla Resumen
    st.subheader("Flujo de Caja Anual Detallado")
    
    # Formatear tabla para mostrar
    tabla_show = df_anual.copy()
    format_cols = ['ingresos', 'cof', 'provisiones', 'opex', 'ebitda', 'interes_prestamo', 'utilidad_neta', 'flujo_caja_equity']
    
    # Aplicar formato de moneda solo para visualización
    st.dataframe(
        tabla_show[format_cols].style.format("${:,.2f}"),
        use_container_width=True
    )
    
    # Descargar Excel
    csv = df_anual.to_csv().encode('utf-8')
    st.download_button(
        "📥 Descargar Proyección Completa (CSV)",
        data=csv,
        file_name="proyeccion_financiera.csv",
        mime="text/csv"
    )
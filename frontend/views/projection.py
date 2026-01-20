import streamlit as st
import pandas as pd
from frontend.utils.financial_logic import run_financial_model, calculate_kpis, create_figures

def render_projection():
    """
    Renderiza la vista del Simulador Financiero.
    """
    # --- INICIALIZAR ESTADO ---
    if 'portfolio_data' not in st.session_state:
        st.session_state.portfolio_data = pd.DataFrame([
            {'País': 'Chile', 'FIU Performing': 86.17, 'FIU NPA': 21.28},
            {'País': 'Perú', 'FIU Performing': 30.67, 'FIU NPA': 21.95},
            {'País': 'Colombia', 'FIU Performing': 97.25, 'FIU NPA': 9.63},
            {'País': 'Brasil', 'FIU Performing': 9.32, 'FIU NPA': 18.44},
        ])

    # Título
    st.markdown('<div class="ns-card"><h4>📉 Simulador Financiero</h4>Configura los parámetros para proyectar la rentabilidad y el flujo de caja.</div>', unsafe_allow_html=True)

    # Layout de 2 columnas: Inputs (Izquierda) | Resultados (Derecha)
    col_config, col_results = st.columns([1, 2])

    # --- COLUMNA IZQUIERDA: CONFIGURACIÓN ---
    with col_config:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        st.markdown("##### 1. Estructura de Capital")
        monto_deuda = st.number_input("Deuda (MUSD)", value=100.0, step=1.0)
        monto_equity = st.number_input("Equity (MUSD)", value=80.0, step=1.0)
        
        st.markdown("##### 2. Términos del Crédito")
        tasa_interes = st.number_input("Tasa Interés Anual (%)", value=10.0, step=0.1)
        plazo_anos = st.number_input("Plazo (Años)", value=5, min_value=1, max_value=30)
        tipo_amortizacion = st.selectbox("Tipo Amortización", ["Amortizado", "Bullet"])

        with st.expander("⚙️ Supuestos Operativos (Avanzado)"):
            revenue_rate = st.number_input("Ingresos / FIU (%)", value=24.0)
            cof_rate = st.number_input("COF / FIU (%)", value=8.6)
            provision_rate = st.number_input("Provisiones (%)", value=2.1)
            recupera_npa = st.number_input("Recup. NPA Anual (%)", value=10.0)
            opex_pct = st.number_input("OPEX (% Ingresos)", value=44.0)
            tax_rate = st.number_input("Impuestos (%)", value=27.0)
        
        st.markdown("---")
        st.markdown("##### 3. Cartera Inicial")
        # Tabla editable para el portafolio
        edited_portfolio = st.data_editor(
            st.session_state.portfolio_data,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "FIU Performing": st.column_config.NumberColumn(format="$%.2f"),
                "FIU NPA": st.column_config.NumberColumn(format="$%.2f")
            },
            key="editor_portfolio"
        )
        st.session_state.portfolio_data = edited_portfolio

        st.write("")
        if st.button("🚀 Ejecutar Simulación", type="primary", use_container_width=True):
            # Lógica de cálculo
            fiu_perf = edited_portfolio['FIU Performing'].sum()
            fiu_npa = edited_portfolio['FIU NPA'].sum()
            
            df_m, df_a = run_financial_model(
                plazo_anos, fiu_perf, fiu_npa, monto_deuda, tasa_interes, tipo_amortizacion,
                revenue_rate, cof_rate, provision_rate, recupera_npa, opex_pct, tax_rate
            )
            kpis = calculate_kpis(df_a, monto_equity, plazo_anos, df_m['saldo_prestamo'])
            figs = create_figures(df_anual=df_a, monto_deuda=monto_deuda)
            
            # Guardar en sesión para persistencia
            st.session_state.sim_results = {'kpis': kpis, 'figs': figs, 'df': df_a}
        
        st.markdown('</div>', unsafe_allow_html=True)

    # --- COLUMNA DERECHA: RESULTADOS ---
    with col_results:
        if 'sim_results' in st.session_state:
            res = st.session_state.sim_results
            
            # Tarjetas de KPIs
            k1, k2, k3 = st.columns(3)
            def kpi_box(label, value, col):
                col.markdown(f"""
                <div style="background:white; padding:15px; border-radius:5px; border-top:3px solid #122442; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
                    <div style="color:#888; font-size:12px;">{label}</div>
                    <div style="color:#122442; font-size:22px; font-weight:bold;">{value}</div>
                </div>
                """, unsafe_allow_html=True)

            kpi_box("ROI s/ Equity", res['kpis']['roi_text'], k1)
            kpi_box("Utilidad Neta Total", res['kpis']['profit_text'], k2)
            kpi_box("Tiempo Payback", res['kpis']['payback_text'], k3)

            st.write("")
            
            # Pestañas para gráficos
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Cartera & PnL", "💰 Flujo de Caja", "📉 Deuda", "📋 Tabla de Datos"])
            
            with tab1:
                st.plotly_chart(res['figs']['cartera'], use_container_width=True)
                st.plotly_chart(res['figs']['pnl'], use_container_width=True)
            
            with tab2:
                st.plotly_chart(res['figs']['flujo'], use_container_width=True)
                
            with tab3:
                st.plotly_chart(res['figs']['loan'], use_container_width=True)
                
            with tab4:
                st.dataframe(res['df'].style.format("${:,.2f}"), use_container_width=True)
        
        else:
            # Estado vacío (Placeholder)
            st.info("👈 Configura los parámetros en el panel izquierdo y presiona 'Ejecutar Simulación' para ver los resultados.")
            st.image("https://cdn.dribbble.com/users/2046015/screenshots/5973727/media/4ff4b63ef7ca0963d666d03b0c60965e.gif", width=300)
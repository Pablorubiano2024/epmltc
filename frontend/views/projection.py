import streamlit as st
import pandas as pd
import numpy as np
from frontend.utils.financial_logic import run_financial_model, format_pnl_display

# --- 1. DATOS BASE FIU (Cartera) ---
BASE_DATA = {
    "Regional": {"perf": 531.41, "npa": 71.30},
    "Chile":    {"perf": 86.17, "npa": 21.28},
    "Perú":     {"perf": 30.67, "npa": 21.95},
    "Colombia": {"perf": 97.25, "npa": 9.63},
    "Brasil":   {"perf": 9.32, "npa": 18.44}
}

# --- 2. DATOS DEUDA REAL ---
REAL_DEBT_DATA = [
    {"Country": "Chile", "Type": "Banking", "USD Balance Equiv": 2777178, "Weighted average annual rate": 7.45, "Plazo": 3},
    {"Country": "Chile", "Type": "B-Notes", "USD Balance Equiv": 835000, "Weighted average annual rate": 11.00, "Plazo": 3},
    {"Country": "Chile", "Type": "Bond", "USD Balance Equiv": 12186466, "Weighted average annual rate": 11.13, "Plazo": 5},
    {"Country": "Chile", "Type": "FIP LTC I", "USD Balance Equiv": 5140426, "Weighted average annual rate": 10.82, "Plazo": 4},
    {"Country": "Chile", "Type": "Intermediation", "USD Balance Equiv": 35995050, "Weighted average annual rate": 8.05, "Plazo": 1},
    {"Country": "Colombia", "Type": "Banking", "USD Balance Equiv": 9827044, "Weighted average annual rate": 11.13, "Plazo": 3},
    {"Country": "Colombia", "Type": "Intermediation", "USD Balance Equiv": 385569, "Weighted average annual rate": 14.92, "Plazo": 1},
    {"Country": "EEUU", "Type": "NATF", "USD Balance Equiv": 78100000, "Weighted average annual rate": 10.00, "Plazo": 5},
    {"Country": "EEUU", "Type": "Senior Note", "USD Balance Equiv": 364304846, "Weighted average annual rate": 4.72, "Plazo": 7},
    {"Country": "EEUU", "Type": "Sp Mbr C", "USD Balance Equiv": 7500000, "Weighted average annual rate": 10.00, "Plazo": 3},
    {"Country": "Perú", "Type": "B-Notes", "USD Balance Equiv": 14362509, "Weighted average annual rate": 13.01, "Plazo": 3},
]

def render_projection():
    st.markdown('<div class="ns-card"><h4>📉 Simulador Financiero & P&L</h4>Proyección estratégica y estructura de capital.</div>', unsafe_allow_html=True)

    # --- A. SELECTOR DE PAÍS ---
    col_filter, col_view = st.columns([1, 1])
    
    with col_filter:
        pais_selected = st.selectbox(
            "Seleccionar Vista:", 
            ["Regional", "Chile", "Colombia", "Perú", "Brasil"],
            index=0
        )
        # Recuperar datos base
        base = BASE_DATA.get(pais_selected, BASE_DATA["Regional"])
        # Cálculo de Peso para Prorrateo USA
        total_regional = BASE_DATA["Regional"]["perf"] + BASE_DATA["Regional"]["npa"]
        total_local = base["perf"] + base["npa"]
        weight = total_local / total_regional if total_regional > 0 else 0

    with col_view:
        view_mode = st.radio("Visualización P&L:", ["Anual", "Mensual"], horizontal=True)

    c_left, c_right = st.columns([1, 2.5])

    # --- B. CONFIGURACIÓN (IZQUIERDA) ---
    with c_left:
        st.markdown("##### 1. Cartera Inicial")
        # Liberados min_value para permitir ajustes libres
        fiu_perf = st.number_input("FIU Performing (MUSD)", value=float(base["perf"]), format="%.2f", min_value=0.0, step=1.0)
        fiu_npa = st.number_input("FIU NPA (MUSD)", value=float(base["npa"]), format="%.2f", min_value=0.0, step=1.0)

        st.markdown("##### 2. Deuda Actual (Editable)")
        
        # --- LÓGICA DE CARGA DE DEUDA ---
        df_full = pd.DataFrame(REAL_DEBT_DATA)
        df_full['USD Balance Equiv'] = df_full['USD Balance Equiv'] / 1_000_000 # Pasar a Millones
        
        if pais_selected == "Regional":
            df_debt = df_full.copy()
        else:
            # 1. Deuda Local
            df_local = df_full[df_full['Country'] == pais_selected].copy()
            # 2. Deuda USA (Prorrateada)
            df_usa = df_full[df_full['Country'] == 'EEUU'].copy()
            df_usa['USD Balance Equiv'] = df_usa['USD Balance Equiv'] * weight
            df_usa['Type'] = df_usa['Type'] + f" ({pais_selected} share)"
            
            df_debt = pd.concat([df_local, df_usa], ignore_index=True)

        current_debt = st.data_editor(
            df_debt,
            column_config={
                "USD Balance Equiv": st.column_config.NumberColumn("Monto (MUSD)", format="$%.2f", min_value=0.0),
                "Weighted average annual rate": st.column_config.NumberColumn("Tasa Anual %", format="%.2f%%", min_value=-100.0, max_value=100.0),
                "Plazo": st.column_config.NumberColumn("Plazo", min_value=0.1, max_value=30.0, step=0.5),
                "Country": None # Ocultar país para ahorrar espacio
            },
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key=f"editor_{pais_selected}"
        )
        
        total_d = current_debt['USD Balance Equiv'].sum()
        st.caption(f"Deuda Total Asignada: ${total_d:,.2f} MUSD")

        st.markdown("##### 3. Nueva Deuda")
        new_debt_amt = st.number_input("Monto (MUSD)", value=0.0, min_value=0.0, step=1.0)
        new_debt_rate = st.number_input("Tasa %", value=10.0, min_value=0.0, step=0.1)
        new_debt_type = st.selectbox("Amortización", ["Amortizado", "Bullet"])
        
        # D. Supuestos Operativos (LIBERADOS)
        with st.expander("⚙️ Drivers Operativos", expanded=False):
            rev_rate = st.number_input("Revenue Rate %", value=24.0, min_value=-100.0, max_value=1000.0, step=0.1)
            cof_rate = st.number_input("COF Rate %", value=8.6, min_value=-100.0, max_value=1000.0, step=0.1)
            prov_rate = st.number_input("Provisiones %", value=2.1, min_value=-100.0, max_value=1000.0, step=0.1)
            opex_pct = st.number_input("OPEX % s/Ingresos", value=44.0, min_value=-100.0, max_value=1000.0, step=0.1)
            rec_npa = st.number_input("Recupero NPA %", value=10.0, min_value=-100.0, max_value=1000.0, step=0.1)
            tax_rate = st.number_input("Tax Rate %", value=27.0, min_value=0.0, max_value=100.0, step=0.1)
            
        with st.expander("📉 P&L Items (MUSD/Año)", expanded=False):
            cogs = st.number_input("COGS", value=0.0, step=0.1)
            dep = st.number_input("Deprec. & Amort.", value=1.5, step=0.1)
            fx = st.number_input("FX Impact", value=0.0, step=0.1)
            non_op = st.number_input("Non-Op Result", value=0.0, step=0.1)

        st.write("")
        run_sim = st.button("🚀 Calcular P&L", type="primary", use_container_width=True)

    # --- C. RESULTADOS (DERECHA) ---
    with c_right:
        if run_sim:
            # 1. Ejecutar Modelo
            df_m, df_a = run_financial_model(
                plazo_anos=5,
                fiu_perf_start=fiu_perf, fiu_npa_start=fiu_npa,
                new_debt_amount=new_debt_amt, new_debt_rate=new_debt_rate, new_debt_type=new_debt_type,
                rev_rate=rev_rate, cof_rate=cof_rate, provision_rate=prov_rate,
                rec_npa_rate=rec_npa, opex_pct=opex_pct, tax_rate=tax_rate,
                cogs_amount=cogs, dep_amort_amount=dep, fx_impact=fx, non_op_result=non_op,
                df_current_debt=current_debt
            )
            
            # 2. Formatear Verticalmente
            df_final = df_m if view_mode == 'Mensual' else df_a
            pnl_view = format_pnl_display(df_final, view_mode)
            
            # 3. Mostrar KPIs Rápidos
            col_k1, col_k2, col_k3 = st.columns(3)
            
            # --- FIX: Nombre de columna corregido a 'Earnings' ---
            total_ni = df_a['Earnings'].sum() 
            avg_ebitda = df_a['EBITDA'].mean()
            fiu_final = df_a['FIU Performing'].iloc[-1] + df_a['FIU NPA'].iloc[-1]
            
            def kpi_card(label, value, col):
                col.markdown(f"""
                <div style="background:white;padding:15px;border-radius:5px;border-left:4px solid #122442;box-shadow:0 1px 3px rgba(0,0,0,0.1);text-align:center;">
                    <div style="color:#666;font-size:12px;">{label}</div>
                    <div style="color:#122442;font-size:20px;font-weight:bold;">{value}</div>
                </div>
                """, unsafe_allow_html=True)
                
            kpi_card("Utilidad Neta Acum. (5Y)", f"${total_ni:,.1f} M", col_k1)
            kpi_card("EBITDA Promedio Anual", f"${avg_ebitda:,.1f} M", col_k2)
            kpi_card("FIU Final (Año 5)", f"${fiu_final:,.1f} M", col_k3)
            
            st.write("")
            
            # 4. Tabla P&L Estilizada
            st.markdown(f"##### Estado de Resultados Proyectado ({view_mode})")
            
            def style_pnl(row):
                if row.name in ['Gross Income', 'Op. Income / EBITDA', 'Earnings before tax (EBT)', 'Earnings (Net Income)', 'Total FIU']:
                    return ['font-weight: bold; background-color: #f0f2f6; color: #122442']*len(row)
                if '%' in row.name:
                    return ['color: #19AC86; font-style: italic']*len(row)
                if pd.isna(row.iloc[0]):
                    return ['background-color: white']*len(row)
                return ['']*len(row)

            st.dataframe(
                pnl_view.style.apply(style_pnl, axis=1).format("{:,.2f}", na_rep=""),
                use_container_width=True,
                height=800
            )
            
            net_margin_start = pnl_view.iloc[-1, 0]
            net_margin_end = pnl_view.iloc[-1, -1]
            st.caption(f"💡 El Margen Neto pasa de {net_margin_start:.1f}% al inicio a {net_margin_end:.1f}% al final del periodo.")

        else:
            st.info("👈 Ajusta los parámetros y la deuda actual, luego presiona 'Calcular P&L'.")
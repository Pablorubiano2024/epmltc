import sys
import os
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from frontend.utils.styles import load_css 

# Paleta Financiera
LTC_PALETTE = ['#122442', '#19AC86', '#FE4A49', '#A2E3EB', '#F4B400', '#DB4437']

@st.cache_data(ttl=300)
def load_data(start_date, end_date):
    API_URL = "http://127.0.0.1:8000/api/v1/opex/transactions"
    empresas_list = "CONIX,GFO,LTCP,LTCP2,NCPF,LEASING,AFI,LTC,NC SPA,NC L,NC SA,IN SA,INCOFIN LEASING,NC LEASING PERU,NC LEASING CHILE"
    
    params = {"start_date": start_date, "end_date": end_date, "empresas": empresas_list, "limit": 0}
    
    try:
        response = requests.get(API_URL, params=params)
        if response.status_code != 200: return pd.DataFrame()

        df = pd.DataFrame(response.json())
        if df.empty: return df
        
        # --- PREPROCESAMIENTO ---
        df['fecha_corte'] = pd.to_datetime(df['fecha_corte'], errors='coerce')
        df = df.dropna(subset=['fecha_corte'])
        df['Mes'] = df['fecha_corte'].dt.strftime('%Y-%m')
        
        # País
        def get_pais(emp):
            e = str(emp).upper().strip()
            if 'CONIX' in e or 'GFO' in e: return 'Colombia 🇨🇴'
            if any(x in e for x in ['LTCP', 'NCPF', 'LEASING PERU']): return 'Perú 🇵🇪'
            return 'Chile 🇨🇱'
        df['Pais'] = df['empresa'].apply(get_pais)
        
        # Limpieza y Formatos
        df['grupo'] = df['grupo'].fillna('Sin Clasificar')
        df['subgrupo'] = df['subgrupo'].fillna('General')
        df['nombre_tercero'] = df['nombre_tercero'].fillna("Sin Proveedor").replace("", "Sin Proveedor")
        df['status_gestion'] = df.get('status_gestion', 'Pendiente').fillna('Pendiente')
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)
        
        return df
    except: return pd.DataFrame()

# --- MOTOR DE ALERTAS FINANCIERAS ---
def analyze_deviations(df):
    """Detecta anomalías y crecimientos sostenidos"""
    if df.empty: return pd.DataFrame()

    # 1. Pivotar por Mes y Proveedor
    pivot = df.groupby(['Mes', 'nombre_tercero'])['valor'].sum().unstack(fill_value=0)
    
    alerts = []
    # Analizar últimos 3 meses disponibles en los datos
    meses_disponibles = sorted(pivot.index.tolist())
    if len(meses_disponibles) < 3: return pd.DataFrame()

    last_3_months = meses_disponibles[-3:]
    
    for proveedor in pivot.columns:
        vals = pivot.loc[last_3_months, proveedor].values
        v1, v2, v3 = vals[0], vals[1], vals[2]
        
        # Regla 1: Crecimiento Sostenido (>100 USD para filtrar ruido)
        if v3 > v2 > v1 and v3 > 100:
            var_pct = ((v3 - v1) / v1) * 100 if v1 != 0 else 100
            alerts.append({
                "Proveedor": proveedor,
                "Tipo Alerta": "📈 Crecimiento Sostenido",
                "Criticidad": "Alta" if v3 > 5000 else "Media",
                "Mes Anterior": v2,
                "Mes Actual": v3,
                "Var % (3M)": var_pct
            })
            
        # Regla 2: Pico repentino (Spike)
        avg_prev = (v1 + v2) / 2
        if v3 > (avg_prev * 1.5) and v3 > 1000: # 50% más que el promedio anterior
             alerts.append({
                "Proveedor": proveedor,
                "Tipo Alerta": "⚡ Pico de Gasto",
                "Criticidad": "Alta",
                "Mes Anterior": avg_prev,
                "Mes Actual": v3,
                "Var % (3M)": ((v3 - avg_prev)/avg_prev)*100
            })

    return pd.DataFrame(alerts)

def render_dashboard():
    # --- FILTROS ---
    st.markdown('<div class="ns-card">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: start = st.date_input("Desde", date(2024, 1, 1))
    with c2: end = st.date_input("Hasta", date(2025, 12, 31))
    
    df_raw = load_data(start, end)
    if df_raw.empty:
        st.warning("⚠️ Sin datos."); st.markdown('</div>', unsafe_allow_html=True); return

    all_paises = sorted(df_raw['Pais'].unique())
    with c3: paises_sel = st.multiselect("País", all_paises, default=all_paises)
    
    df_pais = df_raw[df_raw['Pais'].isin(paises_sel)]
    all_empresas = sorted(df_pais['empresa'].unique())
    with c4: empresas_sel = st.multiselect("Empresa", all_empresas, default=all_empresas)
    
    with c5:
        st.write("")
        if st.button("🔄 Refrescar", use_container_width=True): st.cache_data.clear(); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    df = df_pais[df_pais['empresa'].isin(empresas_sel)]

    # --- ALERTAS INTELIGENTES (TOP SECTION) ---
    alerts = analyze_deviations(df)
    
    if not alerts.empty:
        st.markdown(f"##### 🚨 Alertas de Desviación ({len(alerts)})")
        col_alert_list, col_alert_detail = st.columns([1.5, 2])
        
        with col_alert_list:
            # Seleccionar una alerta para ver detalle
            selected_alert = st.dataframe(
                alerts.sort_values("Mes Actual", ascending=False),
                use_container_width=True,
                height=250,
                selection_mode="single-row",
                on_select="rerun",
                column_config={
                    "Mes Actual": st.column_config.NumberColumn(format="$%d"),
                    "Var % (3M)": st.column_config.NumberColumn(format="%.1f%%"),
                },
                hide_index=True
            )
        
        with col_alert_detail:
            if len(selected_alert.selection.rows) > 0:
                idx = selected_alert.selection.rows[0]
                prov_name = alerts.iloc[idx]["Proveedor"]
                
                # Filtrar data de ese proveedor
                df_prov = df[df['nombre_tercero'] == prov_name]
                df_prov_trend = df_prov.groupby(['Mes', 'grupo'])['valor'].sum().reset_index()
                
                st.markdown(f"**Análisis Profundo:** {prov_name}")
                fig_prov = px.line(
                    df_prov_trend, x='Mes', y='valor', color='grupo', markers=True,
                    title=f"Tendencia por Grupo de Gasto"
                )
                fig_prov.update_layout(height=220, margin=dict(t=30, b=0, l=0, r=0))
                st.plotly_chart(fig_prov, use_container_width=True)
            else:
                st.info("👈 Selecciona una alerta en la tabla para ver el gráfico de tendencia.")
    
    st.write("")

    # --- KPIS PRINCIPALES ---
    total = df['valor'].sum()
    k1, k2, k3, k4 = st.columns(4)
    def kpi(lbl, val, col):
        col.markdown(f"""<div style="background:white;padding:15px;border-radius:5px;border-left:4px solid #122442;box-shadow:0 1px 3px rgba(0,0,0,0.1);"><div style="color:#666;font-size:12px;">{lbl}</div><div style="color:#122442;font-size:22px;font-weight:bold;">{val}</div></div>""", unsafe_allow_html=True)
    
    kpi("Gasto Total (USD)", f"${total:,.0f}", k1)
    kpi("Total Chile", f"${df[df['Pais'].str.contains('Chile')]['valor'].sum():,.0f}", k2)
    kpi("Total Colombia", f"${df[df['Pais'].str.contains('Colombia')]['valor'].sum():,.0f}", k3)
    kpi("Total Perú", f"${df[df['Pais'].str.contains('Perú')]['valor'].sum():,.0f}", k4)

    st.markdown("---")

    # --- VISUALIZACIÓN POR GRUPO/SUBGRUPO ---
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        # Gráfica de Barras por Grupo
        group_data = df.groupby('grupo')['valor'].sum().reset_index().sort_values('valor', ascending=False)
        fig_g = px.bar(group_data.head(10), x='valor', y='grupo', orientation='h', title="<b>Top 10 Grupos de Gasto</b>", text_auto='.2s', color_discrete_sequence=[LTC_PALETTE[0]])
        fig_g.update_layout(yaxis_title=None, xaxis_title="USD")
        st.plotly_chart(fig_g, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        # Tendencia General
        trend = df.groupby('Mes')['valor'].sum().reset_index()
        fig_t = px.area(trend, x='Mes', y='valor', title="<b>Evolución del Gasto Total</b>", color_discrete_sequence=[LTC_PALETTE[1]])
        st.plotly_chart(fig_t, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- GESTIÓN DE PROVEEDORES (WORKFLOW) ---
    st.markdown("### 🛠️ Gestión y Acciones Correctivas")
    
    with st.container():
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        
        # Filtros locales para la tabla de gestión
        cf1, cf2, cf3 = st.columns(3)
        status_filter = cf1.multiselect("Filtrar por Status", ["Pendiente", "En Revisión", "Revisado", "Cerrado"], default=["Pendiente", "En Revisión"])
        prov_search = cf2.text_input("Buscar Proveedor")
        
        # Dataframe para gestión
        df_mgmt = df.copy()
        if status_filter: df_mgmt = df_mgmt[df_mgmt['status_gestion'].isin(status_filter)]
        if prov_search: df_mgmt = df_mgmt[df_mgmt['nombre_tercero'].str.contains(prov_search, case=False)]
        
        # Agrupar para gestión (No mostramos fila por fila, sino agrupado por Proveedor/Mes o Proveedor/Concepto)
        # Para editar status, necesitamos el ID. Así que mostramos el detalle.
        
        df_edit = df_mgmt[['id_transaccion', 'fecha_corte', 'empresa', 'nombre_tercero', 'descripcion_gasto', 'valor', 'grupo', 'status_gestion']].head(200) # Límite por performance
        
        edited_df = st.data_editor(
            df_edit,
            column_config={
                "id_transaccion": st.column_config.NumberColumn("ID", disabled=True),
                "fecha_corte": st.column_config.DateColumn("Fecha"),
                "valor": st.column_config.NumberColumn("Monto", format="$%d"),
                "status_gestion": st.column_config.SelectboxColumn(
                    "Status Gestión",
                    options=["Pendiente", "En Revisión", "Revisado", "Cerrado"],
                    required=True
                )
            },
            use_container_width=True,
            hide_index=True,
            key="editor_gestion"
        )
        
        col_save, _ = st.columns([1, 4])
        if col_save.button("💾 Guardar Cambios de Status", type="primary"):
            with st.spinner("Actualizando..."):
                try:
                    payload = []
                    # Detectar cambios comparando con el original (o mandar todo el lote editado)
                    # Mandamos todo el lote editado por simplicidad
                    for _, row in edited_df.iterrows():
                        payload.append({
                            "id_transaccion": int(row['id_transaccion']),
                            "status_gestion": row['status_gestion']
                        })
                    
                    # Usamos el mismo endpoint de update
                    res = requests.put("http://127.0.0.1:8000/api/v1/opex/update-batch", json=payload)
                    
                    if res.status_code == 200:
                        st.success("✅ Status actualizados.")
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Error: {res.text}")
                except Exception as e: st.error(str(e))

        st.markdown('</div>', unsafe_allow_html=True)
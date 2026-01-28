import sys
import os
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, date
from frontend.utils.styles import load_css 

# Paleta
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
        
        # PREPROCESAMIENTO
        df['fecha_corte'] = pd.to_datetime(df['fecha_corte'], errors='coerce')
        df = df.dropna(subset=['fecha_corte'])
        df['Fecha Corte'] = df['fecha_corte'].dt.strftime('%Y-%m-%d')
        df['Mes'] = df['fecha_corte'].dt.to_period('M')
        
        def get_pais(emp):
            e = str(emp).upper().strip()
            if 'CONIX' in e or 'GFO' in e: return 'Colombia 🇨🇴'
            if any(x in e for x in ['LTCP', 'NCPF', 'LEASING PERU']): return 'Perú 🇵🇪'
            return 'Chile 🇨🇱'
        df['Pais'] = df['empresa'].apply(get_pais)
        
        df['grupo'] = df['grupo'].fillna('Sin Clasificar')
        df['subgrupo'] = df['subgrupo'].fillna('General')
        df['nombre_tercero'] = df['nombre_tercero'].fillna("Sin Proveedor").replace("", "Sin Proveedor")
        df['status_gestion'] = df.get('status_gestion', 'Pendiente').fillna('Pendiente')
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)
        
        return df
    except: return pd.DataFrame()

def analyze_deviations(df):
    if df.empty: return pd.DataFrame()
    df['MesStr'] = df['fecha_corte'].dt.strftime('%Y-%m')
    pivot = df.groupby(['MesStr', 'nombre_tercero'])['valor'].sum().unstack(fill_value=0)
    meses = sorted(pivot.index.tolist())
    if len(meses) < 3: return pd.DataFrame()
    last_3 = meses[-3:]
    
    alerts = []
    for proveedor in pivot.columns:
        vals = pivot.loc[last_3, proveedor].values
        v1, v2, v3 = vals[0], vals[1], vals[2]
        if v3 > v2 > v1 and v3 > 100:
            var_pct = ((v3 - v1) / v1) if v1 != 0 else 1.0
            alerts.append({
                "Proveedor": proveedor,
                "Tendencia": "📈 Crecimiento Sostenido",
                "Mes 1": v1,
                "Mes 2": v2,
                "Mes Actual": v3,
                "Var % (3M)": var_pct
            })
    return pd.DataFrame(alerts)

def render_dashboard():
    # ==========================================================================
    # BARRA DE FILTROS SUPERIOR (INCLUYE PROVEEDOR)
    # ==========================================================================
    st.markdown('<div class="ns-card" style="padding-bottom: 5px;">', unsafe_allow_html=True)
    st.markdown("##### 🔍 Filtros Globales")
    
    # Columnas ajustadas para incluir Proveedor
    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([0.7, 0.7, 0.8, 1, 1, 1, 1.2, 0.4], gap="small")

    with c1: start = st.date_input("Desde", date(2025, 1, 1), label_visibility="collapsed")
    with c2: end = st.date_input("Hasta", date(2025, 12, 31), label_visibility="collapsed")
    
    df_raw = load_data(start, end)
    if df_raw.empty:
        st.warning("⚠️ Sin datos."); st.markdown('</div>', unsafe_allow_html=True); return

    # Filtros Cascada
    with c3: 
        paises_sel = st.multiselect("País", sorted(df_raw['Pais'].unique()), default=sorted(df_raw['Pais'].unique()), placeholder="País", label_visibility="collapsed")
    
    df_l1 = df_raw[df_raw['Pais'].isin(paises_sel)]
    with c4: 
        empresas_sel = st.multiselect("Empresa", sorted(df_l1['empresa'].unique()), default=sorted(df_l1['empresa'].unique()), placeholder="Empresa", label_visibility="collapsed")
    
    df_l2 = df_l1[df_l1['empresa'].isin(empresas_sel)]
    with c5: 
        grupos_sel = st.multiselect("Grupo", sorted(df_l2['grupo'].unique()), default=sorted(df_l2['grupo'].unique()), placeholder="Grupo", label_visibility="collapsed")
    
    df_l3 = df_l2[df_l2['grupo'].isin(grupos_sel)]
    with c6: 
        subgrupos_sel = st.multiselect("Subgrupo", sorted(df_l3['subgrupo'].unique()), default=sorted(df_l3['subgrupo'].unique()), placeholder="Subgrupo", label_visibility="collapsed")
    
    df_l4 = df_l3[df_l3['subgrupo'].isin(subgrupos_sel)]

    # Filtro Proveedor
    with c7:
        all_provs = sorted(df_l4['nombre_tercero'].unique())
        # Default vacío para no filtrar si no se quiere
        provs_sel = st.multiselect("Proveedor", all_provs, placeholder="Buscar Proveedor...", label_visibility="collapsed")

    with c8:
        st.markdown("<div style='margin-top: 2px;'></div>", unsafe_allow_html=True)
        if st.button("🔄", help="Refrescar Datos"): 
            st.cache_data.clear()
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # Aplicar Filtro Final
    df = df_l4.copy()
    if provs_sel:
        df = df[df['nombre_tercero'].isin(provs_sel)]

    # ==========================================================================
    # ALERTAS Y KPIs
    # ==========================================================================
    alerts = analyze_deviations(df)
    if not alerts.empty:
        st.markdown(f"##### 🚨 Alertas de Crecimiento ({len(alerts)})")
        c_alert, c_chart = st.columns([1.5, 2])
        with c_alert:
            alerts_display = alerts.sort_values("Mes Actual", ascending=False).reset_index(drop=True)
            selection = st.dataframe(
                alerts_display, use_container_width=True, height=250, selection_mode="single-row", on_select="rerun",
                column_config={
                    "Mes Actual": st.column_config.NumberColumn(format="$%d"),
                    "Mes 1": st.column_config.NumberColumn(format="$%d"),
                    "Mes 2": st.column_config.NumberColumn(format="$%d"),
                    "Var % (3M)": st.column_config.NumberColumn(format="%.1f%%"),
                }, hide_index=True
            )
        with c_chart:
            if len(selection.selection.rows) > 0:
                idx = selection.selection.rows[0]
                prov_name = alerts_display.iloc[idx]["Proveedor"]
                df_prov = df_raw[df_raw['nombre_tercero'] == prov_name].copy()
                df_prov['MesStr'] = df_prov['fecha_corte'].dt.strftime('%Y-%m')
                df_trend = df_prov.groupby(['MesStr', 'grupo'])['valor'].sum().reset_index()
                st.markdown(f"**Análisis: {prov_name}**")
                fig = px.line(df_trend, x='MesStr', y='valor', color='grupo', markers=True)
                fig.update_layout(yaxis_tickformat="$,.0f", height=220, margin=dict(t=10,b=0,l=0,r=0))
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("👈 Selecciona una alerta para ver el detalle.")
    st.write("")

    # --- KPIs ---
    total = df['valor'].sum()
    k1, k2, k3, k4 = st.columns(4)
    def kpi(lbl, val, col):
        col.markdown(f"""<div style="background:white;padding:15px;border-radius:5px;border-left:4px solid #122442;box-shadow:0 1px 3px rgba(0,0,0,0.1);"><div style="color:#666;font-size:12px;">{lbl}</div><div style="color:#122442;font-size:22px;font-weight:bold;">{val}</div></div>""", unsafe_allow_html=True)
    
    kpi("Gasto Total (USD)", f"${total:,.0f}", k1)
    kpi("Total Chile", f"${df[df['Pais'].str.contains('Chile')]['valor'].sum():,.0f}", k2)
    kpi("Total Colombia", f"${df[df['Pais'].str.contains('Colombia')]['valor'].sum():,.0f}", k3)
    kpi("Total Perú", f"${df[df['Pais'].str.contains('Perú')]['valor'].sum():,.0f}", k4)
    st.markdown("---")

    # ==========================================================================
    # GRÁFICOS
    # ==========================================================================
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        # FIX: Gráfico descendente visualmente (ascending=True para Plotly H-Bar)
        g_data = df.groupby('grupo')['valor'].sum().reset_index().sort_values('valor', ascending=True).tail(10)
        fig_g = px.bar(g_data, x='valor', y='grupo', orientation='h', title="<b>Top Grupos de Gasto</b>", text_auto='.2s', color_discrete_sequence=[LTC_PALETTE[0]])
        fig_g.update_layout(xaxis_tickformat="$,.0f", yaxis_title=None)
        st.plotly_chart(fig_g, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        trend = df.groupby('Mes')['valor'].sum()
        if not trend.empty:
            full_idx = pd.period_range(start=start, end=end, freq='M')
            trend = trend.reindex(full_idx, fill_value=0).reset_index()
            trend.columns = ['Mes', 'valor']
            trend['Mes'] = trend['Mes'].astype(str)
            fig_t = px.area(trend, x='Mes', y='valor', title="<b>Evolución del Gasto</b>", color_discrete_sequence=[LTC_PALETTE[1]])
            fig_t.update_xaxes(type='category')
            st.plotly_chart(fig_t, use_container_width=True)
        else: st.info("Sin datos.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================================================
    # GESTIÓN DE PROVEEDORES (ORDEN Y FORMATO CORREGIDOS)
    # ==========================================================================
    st.markdown("### 🛠️ Gestión y Acciones Correctivas")
    with st.container():
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        
        col_f1, col_f2 = st.columns([1, 2])
        status_filter = col_f1.multiselect("Filtrar Status", ["Pendiente", "En Revisión", "Revisado", "Cerrado"], default=["Pendiente", "En Revisión"])
        
        df_mgmt = df.copy()
        if status_filter: df_mgmt = df_mgmt[df_mgmt['status_gestion'].isin(status_filter)]
        
        # Agrupación Completa
        df_grouped = df_mgmt.groupby('nombre_tercero').agg({
            'valor': 'sum',
            'status_gestion': lambda x: x.mode()[0] if not x.mode().empty else 'Pendiente',
            'grupo': lambda x: x.mode()[0] if not x.mode().empty else 'Sin Clasificar',
            'subgrupo': lambda x: x.mode()[0] if not x.mode().empty else 'General',
            'empresa': lambda x: ', '.join(sorted(x.unique()))
        }).reset_index().sort_values('valor', ascending=False).head(200)

        # Crear columna formateada como Texto para visualización perfecta
        df_grouped['valor_fmt'] = df_grouped['valor'].apply(lambda x: "${:,.0f}".format(x))

        # Reordenar Columnas para el Editor
        # Orden pedido: Empresa | Proveedor | Grupo | Subgrupo | Total Gasto | Status
        cols_ordered = ['empresa', 'nombre_tercero', 'grupo', 'subgrupo', 'valor_fmt', 'status_gestion']

        edited_mgmt = st.data_editor(
            df_grouped[cols_ordered],
            column_config={
                "empresa": st.column_config.TextColumn("Empresa(s)", disabled=True),
                "nombre_tercero": st.column_config.TextColumn("Proveedor", disabled=True),
                "grupo": st.column_config.TextColumn("Grupo", disabled=True),
                "subgrupo": st.column_config.TextColumn("Subgrupo", disabled=True),
                "valor_fmt": st.column_config.TextColumn("Total Gasto", disabled=True),
                "status_gestion": st.column_config.SelectboxColumn("Status", options=["Pendiente", "En Revisión", "Revisado", "Cerrado"], required=True)
            },
            use_container_width=True, hide_index=True, key="mgmt_editor"
        )
        
        if st.button("💾 Guardar Status", type="primary"):
            with st.spinner("Actualizando..."):
                try:
                    payload = []
                    for _, row in edited_mgmt.iterrows():
                        payload.append({"nombre_tercero": row['nombre_tercero'], "status_gestion": row['status_gestion']})
                    res = requests.put("http://127.0.0.1:8000/api/v1/opex/update-provider-status", json=payload)
                    if res.status_code == 200:
                        st.success(f"✅ Se actualizaron {len(payload)} proveedores.")
                        time.sleep(1); st.cache_data.clear(); st.rerun()
                    else: st.error(f"Error: {res.text}")
                except Exception as e: st.error(str(e))
        st.markdown('</div>', unsafe_allow_html=True)
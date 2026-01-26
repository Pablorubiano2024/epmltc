import sys
import os
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, date
from frontend.utils.styles import load_css 

# Paleta de Colores Corporativa (LTC)
LTC_PALETTE = ['#122442', '#19AC86', '#FE4A49', '#A2E3EB', '#6c757d', '#FFC107', '#4285F4']

# ==============================================================================
# FUNCIÓN DE CARGA DE DATOS
# ==============================================================================
@st.cache_data(ttl=300)
def load_data(start_date, end_date):
    """
    Consulta la API de FastAPI y pre-procesa los datos.
    Cache por 5 minutos para velocidad.
    """
    API_URL = "http://127.0.0.1:8000/api/v1/opex/transactions"
    
    # Lista completa de empresas del ETL
    empresas_list = "CONIX,GFO,LTCP,LTCP2,NCPF,LEASING,AFI,LTC,NC SPA,NC L,NC SA,IN SA,INCOFIN LEASING,NC LEASING PERU,NC LEASING CHILE"
    
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "empresas": empresas_list,
        "limit": 0 # IMPORTANTE: 0 para traer TODO sin cortes
    }
    
    try:
        response = requests.get(API_URL, params=params)
        if response.status_code != 200:
            st.error(f"Error API ({response.status_code}): {response.text}")
            return pd.DataFrame()

        data = response.json()
        df = pd.DataFrame(data)
        
        if df.empty: return df
        
        # --- PREPROCESAMIENTO ---
        
        # 1. FIX FECHAS
        df['fecha_corte'] = pd.to_datetime(df['fecha_corte'], errors='coerce')
        df = df.dropna(subset=['fecha_corte'])
        df['Fecha Corte'] = df['fecha_corte'].dt.strftime('%Y-%m-%d')
        # Mes como texto (YYYY-MM) para agrupar gráficas
        df['Mes'] = df['fecha_corte'].dt.strftime('%Y-%m')
        
        # 2. ASIGNACIÓN DE PAÍS (Lógica Actualizada)
        def get_pais(empresa):
            emp = str(empresa).upper().strip()
            
            # COLOMBIA
            if emp in ['CONIX', 'GFO']:
                return 'Colombia 🇨🇴'
            
            # PERÚ
            if emp in ['LTCP', 'LTCP2', 'NCPF', 'NC LEASING PERU']:
                return 'Perú 🇵🇪'
            
            # CHILE (Default para todo lo demás)
            # AFI, LTC, NC SPA, NC SA, NC LEASING CHILE, IN SA, INCOFIN LEASING
            return 'Chile 🇨🇱'
            
        df['Pais'] = df['empresa'].apply(get_pais)
        
        # 3. Limpieza de Nulos y Tipos
        df['Grupo'] = df.get('grupo', pd.Series(['Sin Clasificar']*len(df))).fillna('Sin Clasificar')
        df['Subgrupo'] = df.get('subgrupo', pd.Series(['General']*len(df))).fillna('General')
        df['nombre_tercero'] = df['nombre_tercero'].fillna("Sin Proveedor").replace("", "Sin Proveedor")
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)
        
        return df
        
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame()

# ==============================================================================
# RENDERIZADO DEL DASHBOARD
# ==============================================================================
def render_dashboard():
    # --- BARRA DE HERRAMIENTAS (FILTROS) ---
    st.markdown('<div class="ns-card">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        # Inicio en 2024 para ver GFO si es necesario, o 2025
        start = st.date_input("Desde", date(2024, 1, 1))
    with c2:
        end = st.date_input("Hasta", date(2025, 12, 31))
    
    # Carga Inicial
    df_raw = load_data(start, end)
    
    if df_raw.empty:
        st.warning(f"⚠️ No hay datos entre {start} y {end}.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Filtros Dinámicos
    all_paises = sorted(df_raw['Pais'].unique())
    with c3:
        paises_sel = st.multiselect("País", all_paises, default=all_paises)
    
    # Filtrar empresas disponibles según país seleccionado
    if paises_sel:
        empresas_avail = sorted(df_raw[df_raw['Pais'].isin(paises_sel)]['empresa'].unique())
    else:
        empresas_avail = []
        
    with c4:
        empresas_sel = st.multiselect("Empresa", options=empresas_avail, default=empresas_avail)
    
    with c5:
        st.write("") # Espaciador vertical
        st.write("")
        # --- FIX: LIMPIEZA DE CACHÉ ---
        if st.button("🔄 Refrescar Datos", use_container_width=True):
            st.cache_data.clear() # Borra la memoria para traer datos frescos (positivos)
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # Aplicar Filtros al DataFrame
    df = df_raw.copy()
    if paises_sel: df = df[df['Pais'].isin(paises_sel)]
    if empresas_sel: df = df[df['empresa'].isin(empresas_sel)]

    # --- KPIs ---
    total_usd = df['valor'].sum()
    
    # Totales estáticos para comparación (usando df_raw sin filtros)
    total_chile = df_raw[df_raw['Pais'].str.contains('Chile')]['valor'].sum()
    total_col = df_raw[df_raw['Pais'].str.contains('Colombia')]['valor'].sum()
    total_peru = df_raw[df_raw['Pais'].str.contains('Perú')]['valor'].sum()

    k1, k2, k3, k4 = st.columns(4)
    
    def metric_card(label, value, col, border_color):
        col.markdown(f"""
        <div style="background:white; padding:15px; border-radius:5px; border-top:4px solid {border_color}; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
            <div style="color:#888; font-size:12px; text-transform:uppercase;">{label}</div>
            <div style="color:#122442; font-size:24px; font-weight:bold;">{value}</div>
        </div>
        """, unsafe_allow_html=True)

    metric_card("Total Seleccionado (USD)", f"${total_usd:,.0f}", k1, LTC_PALETTE[0])
    metric_card("Total Chile 🇨🇱", f"${total_chile:,.0f}", k2, LTC_PALETTE[1])
    metric_card("Total Colombia 🇨🇴", f"${total_col:,.0f}", k3, LTC_PALETTE[2])
    metric_card("Total Perú 🇵🇪", f"${total_peru:,.0f}", k4, LTC_PALETTE[3])

    st.write("")

    # ==============================================================================
    # GRÁFICOS FILA 1: TENDENCIA + PAÍS
    # ==============================================================================
    g_row1_1, g_row1_2 = st.columns([2, 1])
    
    with g_row1_1:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        # Agrupar por Mes (Texto YYYY-MM) para barras discretas
        monthly = df.groupby('Mes')['valor'].sum().reset_index().sort_values('Mes')
        
        if not monthly.empty:
            fig = px.bar(
                monthly, 
                x='Mes', 
                y='valor', 
                title="<b>Tendencia Mensual de Gastos</b>", 
                text_auto='.2s',
                color_discrete_sequence=[LTC_PALETTE[0]]
            )
            # Quitamos título del eje X y forzamos layout limpio
            fig.update_xaxes(title=None, type='category') 
            fig.update_layout(yaxis_title="USD", template="plotly_white", height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos mensuales para graficar.")
        st.markdown('</div>', unsafe_allow_html=True)

    with g_row1_2:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        pais_data = df.groupby('Pais')['valor'].sum().reset_index()
        if not pais_data.empty:
            fig2 = px.pie(
                pais_data, 
                values='valor', 
                names='Pais', 
                title="<b>Distribución por País</b>", 
                hole=0.6, 
                color_discrete_sequence=LTC_PALETTE
            )
            fig2.update_layout(
                height=350, 
                margin=dict(t=40, b=20, l=20, r=20),
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ==============================================================================
    # GRÁFICOS FILA 2: EMPRESAS + PROVEEDORES
    # ==============================================================================
    g_row2_1, g_row2_2 = st.columns([1, 1])

    with g_row2_1:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        if not df.empty:
            fig_tree = px.treemap(
                df, 
                path=[px.Constant("Regional"), 'Pais', 'empresa'], 
                values='valor',
                title="<b>Mapa de Calor (Empresas)</b>",
                color='valor', 
                color_continuous_scale='Blues'
            )
            fig_tree.update_layout(height=400, margin=dict(t=40, b=20, l=10, r=10))
            st.plotly_chart(fig_tree, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with g_row2_2:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        if 'nombre_tercero' in df.columns:
            top_prov = df.groupby('nombre_tercero')['valor'].sum().reset_index()
            # Filtramos vacíos
            top_prov = top_prov[top_prov['nombre_tercero'] != "Sin Proveedor"]
            top_prov = top_prov.sort_values('valor', ascending=True).tail(10)
            
            if not top_prov.empty:
                fig_prov = px.bar(
                    top_prov, 
                    x='valor', 
                    y='nombre_tercero', 
                    orientation='h',
                    title="<b>Top 10 Proveedores</b>",
                    text_auto='.2s',
                    color_discrete_sequence=[LTC_PALETTE[1]]
                )
                fig_prov.update_layout(yaxis_title=None, xaxis_title="Monto (USD)", template="plotly_white", height=400)
                st.plotly_chart(fig_prov, use_container_width=True)
            else:
                st.info("No hay datos de proveedores para mostrar.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ==============================================================================
    # TABLA DETALLE
    # ==============================================================================
    st.markdown('<div class="ns-card"><h5>📋 Detalle de Transacciones</h5>', unsafe_allow_html=True)
    
    cols_mostrar = ['Pais', 'empresa', 'Grupo', 'Subgrupo', 'nombre_tercero', 'descripcion_gasto', 'valor', 'Fecha Corte']
    cols_validas = [c for c in cols_mostrar if c in df.columns]

    st.dataframe(
        df[cols_validas].sort_values('valor', ascending=False),
        use_container_width=True,
        height=300,
        column_config={
            "valor": st.column_config.NumberColumn("Monto", format="$%d"),
            "Fecha Corte": st.column_config.TextColumn("Fecha Corte"),
            "descripcion_gasto": st.column_config.TextColumn("Descripción", width="large"),
        },
        hide_index=True
    )
    
    csv = df[cols_validas].to_csv(index=False).encode('utf-8')
    st.download_button("📥 Descargar Data (CSV)", data=csv, file_name="opex_report.csv", mime="text/csv")
    
    st.markdown('</div>', unsafe_allow_html=True)
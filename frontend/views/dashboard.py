import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, date

# Paleta
LTC_PALETTE = ['#122442', '#19AC86', '#FE4A49', '#A2E3EB', '#6c757d']

@st.cache_data(ttl=300)
def load_data(start_date, end_date):
    API_URL = "http://127.0.0.1:8000/api/v1/opex/transactions"
    empresas_list = "CONIX,GFO,LTCP,LTCP2,NCPF,LEASING,AFI,LTC,NC SPA,NC L,NC SA,IN SA,INCOFIN LEASING,NC LEASING PERU,NC LEASING CHILE"
    
    try:
        params = {"start_date": start_date, "end_date": end_date, "empresas": empresas_list}
        response = requests.get(API_URL, params=params)
        if response.status_code != 200: return pd.DataFrame()
        
        df = pd.DataFrame(response.json())
        if df.empty: return df

        # Preprocesamiento
        df['fecha_corte'] = pd.to_datetime(df['fecha_corte'], errors='coerce')
        df['Fecha Corte'] = df['fecha_corte'].dt.strftime('%Y-%m-%d')
        df = df.dropna(subset=['fecha_corte'])
        df['Mes'] = df['fecha_corte'].dt.strftime('%Y-%m')

        def get_pais(empresa):
            emp = str(empresa).upper()
            if 'AFI' in emp or 'PERU' in emp or 'LTCP' in emp: return 'Perú 🇵🇪'
            if 'CONIX' in emp or 'GFO' in emp: return 'Colombia 🇨🇴'
            return 'Chile 🇨🇱'

        df['Pais'] = df['empresa'].apply(get_pais)
        df['Grupo'] = df.get('grupo', pd.Series(['Sin Clasificar']*len(df))).fillna('Sin Clasificar')
        df['Subgrupo'] = df.get('subgrupo', pd.Series(['General']*len(df))).fillna('General')
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def render_dashboard():
    # --- BARRA DE HERRAMIENTAS (Filtros Superiores) ---
    st.markdown('<div class="ns-card">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        start = st.date_input("Desde", date(date.today().year, 1, 1))
    with c2:
        end = st.date_input("Hasta", date.today())
    
    # Carga Inicial
    df_raw = load_data(start, end)
    
    if df_raw.empty:
        st.warning("No hay datos disponibles para este periodo.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Filtros Dinámicos
    all_paises = sorted(df_raw['Pais'].unique())
    with c3:
        paises_sel = st.multiselect("País", all_paises, default=all_paises)
    
    empresas_avail = sorted(df_raw[df_raw['Pais'].isin(paises_sel)]['empresa'].unique())
    with c4:
        empresas_sel = st.multiselect("Empresa", empresas_avail, default=empresas_avail)
    
    with c5:
        st.write("") # Espaciador
        st.write("")
        st.button("🔄 Actualizar")

    st.markdown('</div>', unsafe_allow_html=True)

    # Aplicar Filtros
    df = df_raw.copy()
    if paises_sel: df = df[df['Pais'].isin(paises_sel)]
    if empresas_sel: df = df[df['empresa'].isin(empresas_sel)]

    # --- KPIs ---
    total_usd = df['valor'].sum()
    k1, k2, k3, k4 = st.columns(4)
    
    def metric_card(label, value, col):
        col.markdown(f"""
        <div style="background:white; padding:15px; border-radius:5px; border-left:4px solid #122442; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
            <div style="color:#888; font-size:12px;">{label}</div>
            <div style="color:#122442; font-size:20px; font-weight:bold;">{value}</div>
        </div>
        """, unsafe_allow_html=True)

    metric_card("Total Seleccionado", f"${total_usd:,.0f}", k1)
    metric_card("Total Chile 🇨🇱", f"${df_raw[df_raw['Pais'].str.contains('Chile')]['valor'].sum():,.0f}", k2)
    metric_card("Total Colombia 🇨🇴", f"${df_raw[df_raw['Pais'].str.contains('Colombia')]['valor'].sum():,.0f}", k3)
    metric_card("Total Perú 🇵🇪", f"${df_raw[df_raw['Pais'].str.contains('Perú')]['valor'].sum():,.0f}", k4)

    st.write("")

    # --- GRÁFICOS ---
    g_row1_1, g_row1_2 = st.columns([2, 1])
    
    with g_row1_1:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        monthly = df.groupby('fecha_corte')['valor'].sum().reset_index().sort_values('fecha_corte')
        fig = px.bar(monthly, x='fecha_corte', y='valor', title="Tendencia Mensual", color_discrete_sequence=[LTC_PALETTE[0]])
        fig.update_xaxes(tickformat="%Y-%m-%d", dtick="M1")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with g_row1_2:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        pais_data = df.groupby('Pais')['valor'].sum().reset_index()
        fig2 = px.pie(pais_data, values='valor', names='Pais', title="Distribución País", hole=0.5, color_discrete_sequence=LTC_PALETTE)
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- TABLA ---
    st.markdown('<div class="ns-card"><h5>📋 Detalle Transaccional</h5>', unsafe_allow_html=True)
    st.dataframe(df.sort_values('valor', ascending=False), use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
import sys
import os

# ==============================================================================
# 0. FIX DE IMPORTACIÓN
# ==============================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(frontend_dir)
sys.path.append(root_dir)

# ==============================================================================
# IMPORTS
# ==============================================================================
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, date
from frontend.utils.styles import load_css 

# ==============================================================================
# CONFIGURACIÓN Y ESTILOS
# ==============================================================================
st.set_page_config(page_title="Dashboard OPEX", layout="wide", page_icon="📊")

# Cargar estilos globales y logo
load_css()

# Paleta de Colores Corporativa (LTC)
LTC_PALETTE = ['#122442', '#19AC86', '#FE4A49', '#A2E3EB', '#6c757d']

# ==============================================================================
# FUNCIONES DE CARGA
# ==============================================================================
@st.cache_data(ttl=300)
def load_data(start_date, end_date):
    """Consulta la API de FastAPI y pre-procesa los datos"""
    API_URL = "http://127.0.0.1:8000/api/v1/opex/transactions"
    
    empresas_list = "CONIX,GFO,LTCP,LTCP2,NCPF,LEASING,AFI,LTC,NC SPA,NC L,NC SA,IN SA,INCOFIN LEASING,NC LEASING PERU,NC LEASING CHILE"
    
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "empresas": empresas_list
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
        
        # 1. FIX FECHAS: Usamos 'fecha_corte' que es el cierre de mes (YYYY-MM-DD)
        # Convertimos a datetime
        df['fecha_corte'] = pd.to_datetime(df['fecha_corte'], errors='coerce')
        
        # Creamos una versión String limpia para asegurar que NO salga la hora en las tablas
        df['Fecha Corte'] = df['fecha_corte'].dt.strftime('%Y-%m-%d')
        
        # Eliminamos nulos
        df = df.dropna(subset=['fecha_corte'])
        
        # 2. Asignar País
        def get_pais(empresa):
            emp = str(empresa).upper()
            if 'AFI' in emp or 'PERU' in emp or 'LTCP' in emp: 
                return 'Perú 🇵🇪'
            if 'CONIX' in emp or 'GFO' in emp: 
                return 'Colombia 🇨🇴'
            return 'Chile 🇨🇱'
            
        df['Pais'] = df['empresa'].apply(get_pais)
        
        # 3. Limpieza de Nulos
        df['Grupo'] = df.get('grupo', pd.Series(['Sin Clasificar']*len(df))).fillna('Sin Clasificar')
        df['Subgrupo'] = df.get('subgrupo', pd.Series(['General']*len(df))).fillna('General')
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)
        
        return df
        
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame()

# ==============================================================================
# SIDEBAR (FILTROS)
# ==============================================================================
st.sidebar.title("Filtros")

today = date.today()
year_start = date(today.year, 1, 1)
fecha_corte_input = st.sidebar.date_input("Rango de Fechas (Corte)", (year_start, today))

df_raw = pd.DataFrame()

if isinstance(fecha_corte_input, tuple) and len(fecha_corte_input) == 2:
    start, end = fecha_corte_input
    df_raw = load_data(start, end)
else:
    st.info("Selecciona un rango válido.")
    st.stop()

if df_raw.empty:
    st.warning("⚠️ No hay datos para mostrar en este rango.")
    st.stop()

# Filtros en Cascada
all_paises = sorted(df_raw['Pais'].unique())
paises_sel = st.sidebar.multiselect("País", options=all_paises, default=all_paises)

empresas_avail = sorted(df_raw[df_raw['Pais'].isin(paises_sel)]['empresa'].unique())
empresas_sel = st.sidebar.multiselect("Empresa", options=empresas_avail, default=empresas_avail)

grupos_avail = sorted(df_raw[df_raw['empresa'].isin(empresas_sel)]['Grupo'].unique())
grupos_sel = st.sidebar.multiselect("Grupo", options=grupos_avail, default=grupos_avail)

# Aplicar Filtros
df = df_raw.copy()
if paises_sel: df = df[df['Pais'].isin(paises_sel)]
if empresas_sel: df = df[df['empresa'].isin(empresas_sel)]
if grupos_sel: df = df[df['Grupo'].isin(grupos_sel)]

# ==============================================================================
# KPI CARDS
# ==============================================================================
st.markdown("### 🌎 Resumen Financiero (YTD)")

total_usd = df['valor'].sum()
total_chile = df_raw[df_raw['Pais'].str.contains('Chile')]['valor'].sum()
total_col = df_raw[df_raw['Pais'].str.contains('Colombia')]['valor'].sum()
total_peru = df_raw[df_raw['Pais'].str.contains('Perú')]['valor'].sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Seleccionado", f"${total_usd:,.0f}", "USD")
k2.metric("Total Chile 🇨🇱", f"${total_chile:,.0f}", help="Total País sin filtros")
k3.metric("Total Colombia 🇨🇴", f"${total_col:,.0f}", help="Total País sin filtros")
k4.metric("Total Perú 🇵🇪", f"${total_peru:,.0f}", help="Total País sin filtros")

st.markdown("---")

# ==============================================================================
# GRÁFICOS (Fila 1)
# ==============================================================================
col_left, col_right = st.columns([2, 1])

# A. Tendencia Mensual (CORREGIDO)
# Agrupamos explícitamente por 'fecha_corte' (que es un datetime)
monthly_data = df.groupby('fecha_corte')['valor'].sum().reset_index().sort_values('fecha_corte')

fig_bar = px.bar(
    monthly_data, 
    x='fecha_corte', 
    y='valor',
    text_auto='.2s',
    title="<b>Tendencia Mensual de Gastos (Por Fecha de Corte)</b>",
    color_discrete_sequence=[LTC_PALETTE[0]]
)

# FIX: Forzar formato de fecha en el eje X para quitar la hora
fig_bar.update_xaxes(
    tickformat="%Y-%m-%d",  # Formato Año-Mes-Día
    dtick="M1",             # Mostrar un tick por mes
    title=None
)
fig_bar.update_layout(yaxis_title="Monto (USD)", template="plotly_white")
col_left.plotly_chart(fig_bar, use_container_width=True)

# B. Donut por País
country_data = df.groupby('Pais')['valor'].sum().reset_index()
fig_donut = px.pie(
    country_data, values='valor', names='Pais',
    title="<b>Distribución por País</b>",
    hole=0.5,
    color_discrete_sequence=LTC_PALETTE
)
col_right.plotly_chart(fig_donut, use_container_width=True)

# ==============================================================================
# GRÁFICOS (Fila 2)
# ==============================================================================
c1, c2 = st.columns(2)

# C. Detalle por Empresa
fig_tree = px.treemap(
    df, path=[px.Constant("Regional"), 'Pais', 'empresa'], values='valor',
    title="<b>Mapa de Calor por Empresa</b>",
    color='valor', color_continuous_scale='Blues'
)
c1.plotly_chart(fig_tree, use_container_width=True)

# D. Top Proveedores
if 'nombre_tercero' in df.columns:
    top_prov = df.groupby('nombre_tercero')['valor'].sum().reset_index().sort_values('valor', ascending=True).tail(10)
    fig_prov = px.bar(
        top_prov, x='valor', y='nombre_tercero', orientation='h',
        title="<b>Top 10 Proveedores</b>",
        text_auto='.2s',
        color_discrete_sequence=[LTC_PALETTE[1]]
    )
    fig_prov.update_layout(yaxis_title=None, xaxis_title="USD", template="plotly_white")
    c2.plotly_chart(fig_prov, use_container_width=True)

# ==============================================================================
# TABLA DETALLE
# ==============================================================================
st.markdown("### 📋 Detalle de Transacciones")

cols_mostrar = ['Pais', 'empresa', 'Grupo', 'Subgrupo', 'nombre_tercero', 'descripcion_gasto', 'valor', 'Fecha Corte']
cols_validas = [c for c in cols_mostrar if c in df.columns]

st.dataframe(
    df[cols_validas].sort_values('valor', ascending=False),
    use_container_width=True,
    height=400,
    column_config={
        "valor": st.column_config.NumberColumn("Monto", format="$%d"),
        "Fecha Corte": st.column_config.TextColumn("Fecha Corte"), # Usamos la versión string limpia
    },
    hide_index=True
)

# Botón Descarga
csv = df[cols_validas].to_csv(index=False).encode('utf-8')
st.download_button(
    "📥 Descargar Data (CSV)",
    data=csv,
    file_name="opex_report.csv",
    mime="text/csv"
)
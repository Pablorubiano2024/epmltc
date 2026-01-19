import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ==============================================================================
st.set_page_config(page_title="Dashboard OPEX", layout="wide", page_icon="📊")

# CSS Personalizado para tarjetas estilo "Power BI"
st.markdown("""
<style>
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 10px;
    }
    .metric-title {
        color: #666;
        font-size: 14px;
        font-weight: 500;
    }
    .metric-value {
        color: #000;
        font-size: 26px;
        font-weight: bold;
    }
    .metric-sub {
        color: #999;
        font-size: 12px;
    }
    [data-testid="stSidebar"] {
        background-color: #F8F9FA;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNCIONES DE CARGA Y PROCESAMIENTO
# ==============================================================================

@st.cache_data(ttl=300) # Cache por 5 minutos
def load_data(start_date, end_date):
    """Consulta la API de FastAPI"""
    # URL de tu Backend
    API_URL = "http://127.0.0.1:8000/api/v1/opex/transactions"
    
    # Lista de todas las empresas posibles para que la API traiga todo
    empresas_list = "CONIX,GFO,LTCP,LTCP2,NCPF,LEASING,AFI,LTC,NC SPA,NC L,NC SA,IN SA,INCOFIN LEASING,NC LEASING PERU,NC LEASING CHILE"
    
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "empresas": empresas_list
    }
    
    try:
        response = requests.get(API_URL, params=params)
        
        # Si la API falla, lanzamos error controlado
        if response.status_code != 200:
            st.error(f"Error del servidor (Código {response.status_code}): {response.text}")
            return pd.DataFrame()

        data = response.json()
        df = pd.DataFrame(data)
        
        if df.empty: return df
        
        # --- PREPROCESAMIENTO ---
        
        # 1. FIX DE FECHAS (CORRECCIÓN PRINCIPAL)
        # Usamos format='mixed' para que acepte tanto "2025-01-01" como "2025-01-01 00:00:00"
        df['fecha_transaccion'] = pd.to_datetime(df['fecha_transaccion'], format='mixed', errors='coerce')
        
        # Eliminar filas donde la fecha no se pudo leer (NaT)
        df = df.dropna(subset=['fecha_transaccion'])
        
        df['Mes'] = df['fecha_transaccion'].dt.strftime('%Y-%m')
        
        # 2. Asignar País (Lógica de Negocio Mejorada)
        def get_pais(empresa):
            emp = str(empresa).upper()
            if 'AFI' in emp or 'PERU' in emp or 'LTCP' in emp: 
                return 'Perú 🇵🇪'
            if 'CONIX' in emp or 'GFO' in emp: 
                return 'Colombia 🇨🇴'
            return 'Chile 🇨🇱' # Default (LTC, NC, Incofin)
            
        df['Pais'] = df['empresa'].apply(get_pais)
        
        # 3. Validar columnas de Clasificación
        if 'grupo' not in df.columns: df['Grupo'] = "Sin Clasificar"
        else: df['Grupo'] = df['grupo'].fillna("Sin Clasificar")
            
        if 'subgrupo' not in df.columns: df['Subgrupo'] = "General"
        else: df['Subgrupo'] = df['subgrupo'].fillna("General")
            
        # 4. Asegurar numéricos
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)
        
        return df
        
    except Exception as e:
        st.error(f"Error conectando con el servidor: {e}")
        return pd.DataFrame()

# ==============================================================================
# 3. SIDEBAR (FILTROS)
# ==============================================================================
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2830/2830175.png", width=50)
st.sidebar.title("Filtros")

# Fechas
today = date.today()
year_start = date(today.year, 1, 1) # Inicio de este año
fecha_corte = st.sidebar.date_input("Fecha de Corte", (year_start, today))

df_raw = pd.DataFrame() # Inicializar vacío

if isinstance(fecha_corte, tuple) and len(fecha_corte) == 2:
    start, end = fecha_corte
    # Cargar Datos
    df_raw = load_data(start, end)
else:
    st.info("Selecciona un rango de fechas válido para comenzar.")
    st.stop()

if df_raw.empty:
    st.warning("⚠️ No hay datos para el rango seleccionado. Verifica que el ETL haya cargado datos para estas fechas.")
    st.stop()

# Filtros Dinámicos
all_paises = sorted(df_raw['Pais'].unique())
paises_sel = st.sidebar.multiselect("País", options=all_paises, default=all_paises)

# Filtrar empresas basado en países seleccionados
empresas_disponibles = sorted(df_raw[df_raw['Pais'].isin(paises_sel)]['empresa'].unique())
empresas_sel = st.sidebar.multiselect("Empresa", options=empresas_disponibles, default=empresas_disponibles)

# Filtrar grupos
grupos_disponibles = sorted(df_raw[df_raw['empresa'].isin(empresas_sel)]['Grupo'].unique())
grupos_sel = st.sidebar.multiselect("Grupo", options=grupos_disponibles, default=grupos_disponibles)

# Aplicar Filtros al DataFrame Principal
df = df_raw.copy()
if paises_sel: df = df[df['Pais'].isin(paises_sel)]
if empresas_sel: df = df[df['empresa'].isin(empresas_sel)]
if grupos_sel: df = df[df['Grupo'].isin(grupos_sel)]

# ==============================================================================
# 4. CABECERA (KPI CARDS)
# ==============================================================================
st.markdown(f"### Análisis OPEX Regional (USD)")
st.markdown("---")

total_usd = df['valor'].sum()
# Calculamos totales por país usando el DataFrame ORIGINAL (sin filtros) para comparar
total_chile = df_raw[df_raw['Pais'].str.contains('Chile')]['valor'].sum()
total_col = df_raw[df_raw['Pais'].str.contains('Colombia')]['valor'].sum()
total_peru = df_raw[df_raw['Pais'].str.contains('Perú')]['valor'].sum()

def card(title, value, flag):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">{flag} {title}</div>
        <div class="metric-value">${value:,.0f}</div>
        <div class="metric-sub">Acumulado USD</div>
    </div>
    """, unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1: card("Total Seleccionado", total_usd, "🌎")
with c2: card("Total Chile", total_chile, "🇨🇱")
with c3: card("Total Colombia", total_col, "🇨🇴")
with c4: card("Total Perú", total_peru, "🇵🇪")

# ==============================================================================
# 5. GRÁFICOS NIVEL 1 (TENDENCIAS)
# ==============================================================================
st.write(" ") # Espacio
col_left, col_right = st.columns([2, 1])

# A. Comportamiento Regional (Barras Mensuales)
monthly_data = df.groupby('Mes')['valor'].sum().reset_index()

fig_bar = px.bar(
    monthly_data, x='Mes', y='valor',
    text_auto='.2s',
    title="<b>Comportamiento Regional Gasto</b> (Por Mes)",
    color_discrete_sequence=['#4285F4']
)
fig_bar.update_layout(yaxis_title="USD", xaxis_title="", template="plotly_white")
col_left.plotly_chart(fig_bar, use_container_width=True)

# B. Participación por País (Dona)
country_data = df.groupby('Pais')['valor'].sum().reset_index()

fig_donut = px.pie(
    country_data, values='valor', names='Pais',
    title="<b>Participación del Gasto</b> (Selección)",
    hole=0.4,
    color_discrete_sequence=px.colors.qualitative.Pastel
)
col_right.plotly_chart(fig_donut, use_container_width=True)

# ==============================================================================
# 6. GRÁFICOS NIVEL 2 (DETALLE COMPLEJO)
# ==============================================================================
col_bottom_1, col_bottom_2 = st.columns([1, 1])

# C. Evolución por País (Líneas)
monthly_country = df.groupby(['Mes', 'Pais'])['valor'].sum().reset_index()

fig_line = px.line(
    monthly_country, x='Mes', y='valor', color='Pais',
    title="<b>Evolución de Gasto por País</b>",
    markers=True,
    color_discrete_sequence=px.colors.qualitative.Safe
)
fig_line.update_layout(template="plotly_white", yaxis_title="USD", xaxis_title="")
col_bottom_1.plotly_chart(fig_line, use_container_width=True)

# D. Top Proveedores (Barras Horizontales)
if 'nombre_tercero' in df.columns:
    top_prov = df.groupby('nombre_tercero')['valor'].sum().reset_index().sort_values('valor', ascending=True).tail(10)
    
    fig_prov = px.bar(
        top_prov, x='valor', y='nombre_tercero',
        orientation='h',
        title="<b>Top 10 Proveedores (Gasto Regional)</b>",
        text_auto='.2s',
        color_discrete_sequence=['#0F9D58']
    )
    fig_prov.update_layout(yaxis_title="", xaxis_title="USD", template="plotly_white")
    col_bottom_2.plotly_chart(fig_prov, use_container_width=True)

# ==============================================================================
# 7. TABLA DE DETALLE
# ==============================================================================
st.markdown("---")
st.subheader("Detalle de Transacciones")

# Definir columnas a mostrar
cols_to_show = ['Pais', 'empresa', 'Grupo', 'Subgrupo', 'nombre_tercero', 'descripcion_gasto', 'valor', 'fecha_transaccion']
# Filtrar solo las que existen en el DF para evitar errores
cols_existentes = [c for c in cols_to_show if c in df.columns]

df_display = df[cols_existentes].copy()
df_display = df_display.sort_values('valor', ascending=False)

st.dataframe(
    df_display,
    use_container_width=True,
    height=400,
    column_config={
        "valor": st.column_config.NumberColumn("Monto USD", format="$%d"),
        "fecha_transaccion": st.column_config.DateColumn("Fecha"),
        "descripcion_gasto": st.column_config.TextColumn("Detalle", width="medium"),
    },
    hide_index=True
)
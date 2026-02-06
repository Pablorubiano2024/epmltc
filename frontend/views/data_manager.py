import streamlit as st
import pandas as pd
import requests
from datetime import date
from pandas.tseries.offsets import MonthEnd

API_URL = "http://127.0.0.1:8000/api/v1/finance"

# ==============================================================================
# DEFINICIÓN DE PLANTILLAS (CONCEPTOS POR DEFECTO)
# ==============================================================================

# 1. FIU (Cartera)
TEMPLATE_FIU = [
    "FIU Performing", 
    "FIU NPA"
]

# 2. P&L (Datos de Cierre)
TEMPLATE_PNL = [
    "Revenues",
    "Provisions & Writes off",
    "COF",
    "COGS",
    "OPEX",
    "Depreciation & Amortization",
    "Exchange rates",
    "Non operating rev/expenses",
    "Taxes"
]

# 3. DEUDA (Instrumentos del Simulador)
# Nota: Aquí guardaremos el Saldo (Monto).
TEMPLATE_DEUDA = [
    "Banking",
    "B-Notes",
    "Bond",
    "FIP LTC I",
    "Intermediation",
    "NATF",
    "Senior Note",
    "Sp Mbr C"
]

# 4. TIPO DE CAMBIO (Regional)
TEMPLATE_FX = [
    "USD/CLP", 
    "USD/COP", 
    "USD/PEN", 
    "USD/BRL"
]

# ==============================================================================
# RENDERIZADO DE LA VISTA
# ==============================================================================
def render_data_manager():
    # --- HEADER ---
    st.markdown('<div class="ns-card"><h4>💾 Gestor de Datos Maestros (Cierre Mensual)</h4>Ingreso de parámetros financieros reales para alimentar proyecciones.</div>', unsafe_allow_html=True)

    # --- 1. BARRA DE FILTROS SUPERIOR ---
    st.markdown('<div class="ns-card" style="padding: 15px;">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 2])
    
    with c1:
        # Por defecto el último día del mes actual
        default_date = date.today() + MonthEnd(0)
        fecha_input = st.date_input("Fecha de Corte", default_date)
        # Asegurar que sea string YYYY-MM-DD
        fecha_corte = fecha_input.strftime("%Y-%m-%d")

    with c2:
        pais_sel = st.selectbox("País", ["Chile", "Colombia", "Perú", "Brasil"])

    with c3:
        st.info(f"📅 Editando datos para: **{pais_selected_flag(pais_sel)} {pais_sel}** al **{fecha_corte}**")

    st.markdown('</div>', unsafe_allow_html=True)

    # --- 2. CARGAR DATOS EXISTENTES ---
    # Consultamos a la BD si ya existe algo guardado para esa fecha
    try:
        params = {"fecha_corte": fecha_corte, "pais": "Todos"} 
        res = requests.get(f"{API_URL}/params", params=params)
        df_db = pd.DataFrame(res.json()) if res.status_code == 200 else pd.DataFrame()
    except:
        df_db = pd.DataFrame()

    # --- 3. GESTIÓN DE PESTAÑAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["🌎 1. FIU", "📉 2. Datos Cierre P&L", "💰 3. Deuda", "💱 4. Tipo de Cambio"])

    # Función helper para preparar la tabla de edición
    def prepare_editor_df(categoria, template_conceptos, is_fx=False):
        # Si es FX, no filtramos por país (es regional). Si es otro, filtramos por el país seleccionado.
        filter_pais = pais_sel if not is_fx else "Regional"
        
        # Filtrar datos de la BD
        if not df_db.empty:
            if is_fx:
                current_data = df_db[df_db['categoria'] == categoria]
            else:
                current_data = df_db[(df_db['categoria'] == categoria) & (df_db['pais'] == filter_pais)]
        else:
            current_data = pd.DataFrame()

        # Crear estructura base con la plantilla
        df_template = pd.DataFrame({'concepto': template_conceptos})
        
        if not current_data.empty:
            # Merge para traer valores existentes
            df_final = pd.merge(df_template, current_data[['concepto', 'valor', 'descripcion']], on='concepto', how='left')
        else:
            df_final = df_template
            df_final['valor'] = 0.0
            df_final['descripcion'] = ""

        # Llenar nulos
        df_final['valor'] = df_final['valor'].fillna(0.0)
        df_final['descripcion'] = df_final['descripcion'].fillna("")
        
        # Añadir columnas de contexto para guardar después
        df_final['pais'] = filter_pais
        df_final['categoria'] = categoria
        
        return df_final

    # --- PESTAÑA 1: FIU ---
    with tab1:
        st.caption("Ingrese los saldos de cartera al cierre.")
        df_fiu = prepare_editor_df("FIU", TEMPLATE_FIU)
        render_editor(df_fiu, "FIU", fecha_corte)

    # --- PESTAÑA 2: P&L ---
    with tab2:
        st.caption("Ingrese los resultados acumulados del mes (Year-to-Date o Mensual según su estándar).")
        df_pnl = prepare_editor_df("PL_Close", TEMPLATE_PNL)
        render_editor(df_pnl, "PL_Close", fecha_corte)

    # --- PESTAÑA 3: DEUDA ---
    with tab3:
        st.caption("Ingrese el saldo (Monto Principal) de la deuda vigente por instrumento.")
        df_debt = prepare_editor_df("Deuda", TEMPLATE_DEUDA)
        render_editor(df_debt, "Deuda", fecha_corte)

    # --- PESTAÑA 4: TIPO DE CAMBIO (Regional) ---
    with tab4:
        st.caption("Tipos de cambio de cierre (Regional).")
        df_fx = prepare_editor_df("Macro", TEMPLATE_FX, is_fx=True)
        render_editor(df_fx, "Macro", fecha_corte)

def render_editor(df, key_suffix, fecha_corte):
    """Renderiza la tabla editable y el botón de guardar"""
    
    edited_df = st.data_editor(
        df,
        column_config={
            "concepto": st.column_config.TextColumn("Concepto", disabled=True),
            "valor": st.column_config.NumberColumn("Valor (MUSD / Tasa)", format="%.4f", required=True),
            "descripcion": st.column_config.TextColumn("Notas / Fuente"),
            "pais": None, # Ocultar
            "categoria": None # Ocultar
        },
        use_container_width=True,
        hide_index=True,
        key=f"editor_{key_suffix}"
    )

    if st.button(f"💾 Guardar Datos ({key_suffix})", type="primary"):
        with st.spinner("Guardando en Base de Datos..."):
            payload = []
            for _, row in edited_df.iterrows():
                payload.append({
                    "fecha_corte": fecha_corte,
                    "pais": row['pais'],
                    "categoria": row['categoria'],
                    "concepto": row['concepto'],
                    "valor": float(row['valor']),
                    "descripcion": row['descripcion']
                })
            
            try:
                # Enviar al Backend
                r = requests.post(f"{API_URL}/params", json=payload)
                if r.status_code == 200:
                    st.toast(f"Datos de {key_suffix} guardados correctamente!", icon="✅")
                    # Recargar caché silenciosamente si fuera necesario
                else:
                    st.error(f"Error: {r.text}")
            except Exception as e:
                st.error(f"Error de conexión: {e}")

def pais_selected_flag(pais):
    if pais == 'Chile': return '🇨🇱'
    if pais == 'Colombia': return '🇨🇴'
    if pais == 'Perú': return '🇵🇪'
    if pais == 'Brasil': return '🇧🇷'
    return '🌎'
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# Configuración de página
st.set_page_config(page_title="Explorador OPEX", layout="wide")

st.title("🔍 Explorador de Datos OPEX")
st.markdown("Consulta el detalle de transacciones, filtra por criterios y exporta la información.")

# --- SIDEBAR: FILTROS ---
st.sidebar.header("Filtros de Búsqueda")

# 1. Filtro de Fechas
today = datetime.today()
start_date = st.sidebar.date_input("Fecha Inicio", today.replace(day=1))
end_date = st.sidebar.date_input("Fecha Fin", today)

# 2. Filtro de Empresa (Se llena dinámicamente si la API responde, si no, usa estáticos)
empresas_default = ['CONIX', 'GFO', 'LTCP', 'LTCP2', 'NCPF', 'LEASING', 'AFI', 'LTC', 'NC SPA', 'NC L', 'NC SA', 'IN SA', 'IN L']
selected_empresas = st.sidebar.multiselect("Empresas", options=empresas_default, default=empresas_default)

# 3. Filtro de Cuenta
cuenta_filter = st.sidebar.text_input("Filtrar por Cuenta (ej: 5105)", "")

# Botón de Actualizar
btn_buscar = st.sidebar.button("🔎 Buscar Datos", type="primary")

# --- LÓGICA PRINCIPAL ---
if btn_buscar:
    with st.spinner('Consultando base de datos unificada...'):
        try:
            # Construcción de parámetros para la API
            params = {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "empresas": ",".join(selected_empresas), # Enviamos lista separada por comas
                "cuenta": cuenta_filter
            }
            
            # LLAMADA A TU FASTAPI (Ajusta la URL si es necesario)
            # Nota: Necesitarás crear este endpoint en el backend
            api_url = "http://127.0.0.1:8000/api/v1/opex/transactions"
            response = requests.get(api_url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                df = pd.DataFrame(data)
                
                if not df.empty:
                    # Mostrar KPIs rápidos
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Registros Encontrados", len(df))
                    col2.metric("Total Valor", f"${df['valor'].sum():,.0f}")
                    col3.metric("Empresas", df['empresa'].nunique())
                    
                    # Tabla Interactiva
                    st.dataframe(
                        df, 
                        use_container_width=True,
                        column_config={
                            "valor": st.column_config.NumberColumn("Valor", format="$%d"),
                            "fecha_transaccion": st.column_config.DateColumn("Fecha"),
                        },
                        hide_index=True
                    )
                    
                    # Botón de Descarga
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "⬇️ Descargar Reporte (CSV)",
                        data=csv,
                        file_name=f"opex_export_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                    )
                else:
                    st.warning("No se encontraron datos con esos filtros.")
            else:
                st.error(f"Error del servidor: {response.status_code}")

        except Exception as e:
            st.error(f"No se pudo conectar con el Backend: {e}")
else:
    st.info("👈 Selecciona los filtros en la barra lateral y presiona 'Buscar Datos'.")
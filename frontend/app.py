import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="EPM Latam Trade Capital",
    page_icon="📈",
    layout="wide"
)

# Título y Bienvenida
st.title("📈 EPM Latam Trade Capital")
st.markdown("### Sistema de Gestión de Desempeño Empresarial")

st.info("Bienvenido al módulo de control financiero. Selecciona una herramienta en el menú de la izquierda.")

# Dashboard de resumen
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### 📊 Dashboard OPEX
    Visualiza la evolución de gastos, distribución por empresa y tendencias mensuales.
    """)

with col2:
    st.markdown("""
    ### 🔍 Explorador de Datos
    Consulta el detalle de cada transacción, filtra por proveedor, cuenta o fecha y descarga reportes.
    """)

with col3:
    st.markdown("""
    ### 🤖 Clasificador IA
    Utiliza Inteligencia Artificial para categorizar automáticamente los gastos nuevos o sin clasificar.
    """)

st.divider()
st.caption("v1.0 | Desarrollado con FastAPI + Streamlit + Machine Learning")
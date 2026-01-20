import streamlit as st
from frontend.utils.styles import load_css # Importamos nuestro estilo

# Configuración inicial
st.set_page_config(
    page_title="EPM Latam Trade Capital",
    page_icon="assets/favicon.png", # Usamos el favicon
    layout="wide"
)

# Cargar Estilos y Logo
load_css()

# --- HERO SECTION (Bienvenida) ---
col_logo, col_text = st.columns([1, 4])

with col_text:
    st.title("Sistema de Gestión EPM")
    st.markdown("#### **Latam Trade Capital** | Control Financiero & Operativo")
    st.markdown("Bienvenido al portal centralizado de gestión. Seleccione un módulo en el menú lateral para comenzar.")

st.markdown("---")

# --- TARJETAS DE NAVEGACIÓN ---
# Usamos columnas para crear un menú visual en el centro
c1, c2, c3 = st.columns(3)

with c1:
    with st.container(border=True):
        st.header("📊 Dashboard OPEX")
        st.markdown("Visualización de gastos operativos, tendencias mensuales y distribución por centro de costo.")
        st.info("Ideal para: Gerencia Financiera")

with c2:
    with st.container(border=True):
        st.header("🤖 Clasificador IA")
        st.markdown("Motor de Inteligencia Artificial para categorizar gastos automáticamente según el histórico.")
        st.info("Ideal para: Equipo Contable")

with c3:
    with st.container(border=True):
        st.header("📈 Proyección")
        st.markdown("Simulador financiero para evaluación de compra de carteras y flujos de caja futuros.")
        st.info("Ideal para: Planeación Financiera")

st.markdown("---")
st.caption("© 2025 Latam Trade Capital | Powered by Data Analytics Team")
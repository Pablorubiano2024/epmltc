import sys
import os

# ==============================================================================
# 0. FIX DE IMPORTACIÓN (CRÍTICO)
# ==============================================================================
# Esto permite que Python encuentre la carpeta 'frontend' sin importar desde dónde se ejecute
current_dir = os.path.dirname(os.path.abspath(__file__)) # carpeta frontend/
root_dir = os.path.dirname(current_dir) # carpeta raiz epmltc/
sys.path.append(root_dir)

# ==============================================================================
# IMPORTS
# ==============================================================================
import streamlit as st
from streamlit_option_menu import option_menu
from PIL import Image

# Importar estilos y componentes visuales
from frontend.utils.enterprise_style import apply_enterprise_style, render_header

# Importar las Vistas (Módulos)
from frontend.views.dashboard import render_dashboard
from frontend.views.explorer import render_explorer
from frontend.views.classifier import render_classifier
from frontend.views.projection import render_projection
from frontend.views.data_manager import render_data_manager

# ==============================================================================
# CONFIGURACIÓN INICIAL
# ==============================================================================
st.set_page_config(
    page_title="EPM Enterprise", 
    layout="wide", 
    page_icon="🏢",
    initial_sidebar_state="collapsed" # Ocultar sidebar nativo
)

# Aplicar CSS Corporativo
apply_enterprise_style()

# ==============================================================================
# BARRA DE NAVEGACIÓN SUPERIOR (NAVBAR)
# ==============================================================================
with st.container():
    # Grid: [Logo (20%)] | [Menú (60%)] | [Espacio (20%)]
    col_logo, col_menu, col_spacer = st.columns([1.5, 6, 1.5], gap="small")

    # --- 1. LOGO ---
    with col_logo:
        logo_path = os.path.join(root_dir, "assets", "logo_LTC.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=160)
        else:
            st.markdown("### 🏢 **LTC**")

    # --- 2. MENÚ CENTRADO ---
    with col_menu:
        selected = option_menu(
            menu_title=None,
            # Lista de Módulos (Incluyendo el Gestor de Datos)
            options=["Dashboard", "Explorador", "Clasificador IA", "Simulador", "Gestor Datos"],
            # Iconos de Bootstrap Icons (https://icons.getbootstrap.com/)
            icons=["bar-chart-fill", "table", "robot", "graph-up-arrow", "database"],
            menu_icon="cast",
            default_index=0,
            orientation="horizontal",
            styles={
                "container": {
                    "padding": "0!important", 
                    "background-color": "transparent", 
                    "margin": "0"
                },
                "icon": {
                    "color": "#19AC86", 
                    "font-size": "14px"
                }, 
                "nav-link": {
                    "font-size": "14px", 
                    "text-align": "center", 
                    "margin": "0px 5px", 
                    "--hover-color": "#f0f2f6"
                },
                "nav-link-selected": {
                    "background-color": "#122442", 
                    "color": "white", 
                    "font-weight": "600",
                    "border-radius": "5px"
                },
            }
        )
    
    # --- 3. ESPACIO DERECHO ---
    with col_spacer:
        st.write("") # Espaciador vacío

# Línea divisoria sutil
st.markdown("<div style='height: 2px; background-color: #e0e0e0; margin-bottom: 25px;'></div>", unsafe_allow_html=True)

# ==============================================================================
# ENRUTADOR DE VISTAS (CONTROLADOR)
# ==============================================================================

if selected == "Dashboard":
    render_header("Dashboard Operativo")
    render_dashboard()

elif selected == "Explorador":
    render_header("Explorador de Datos")
    render_explorer()

elif selected == "Clasificador IA":
    render_header("Inteligencia Artificial")
    render_classifier()

elif selected == "Simulador":
    render_header("Proyección Financiera")
    render_projection()

elif selected == "Gestor Datos":
    render_header("Administración de Parámetros")
    render_data_manager()
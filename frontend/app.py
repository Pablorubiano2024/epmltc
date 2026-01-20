import sys
import os

# ==============================================================================
# 0. FIX DE IMPORTACIÓN (CRÍTICO)
# ==============================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

# ==============================================================================
# IMPORTS
# ==============================================================================
import streamlit as st
from streamlit_option_menu import option_menu
from PIL import Image

# Imports de vistas
from frontend.utils.enterprise_style import apply_enterprise_style, render_header
from frontend.views.dashboard import render_dashboard
from frontend.views.classifier import render_classifier
from frontend.views.projection import render_projection
from frontend.views.explorer import render_explorer

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
st.set_page_config(
    page_title="EPM Enterprise", 
    layout="wide", 
    page_icon="assets/favicon.png" # Asegúrate de tener este icono también o bórralo
)

# Aplicar estilos CSS globales
apply_enterprise_style()

# ==============================================================================
# NAVBAR PERSONALIZADO (LOGO + MENÚ CENTRADO)
# ==============================================================================
# Contenedor superior con fondo blanco para simular la barra de navegación
with st.container():
    # Definimos 3 columnas: [Logo (pequeño) | Menú (Grande y centrado) | Espacio (pequeño)]
    col_logo, col_menu, col_spacer = st.columns([1.5, 6, 1.5], gap="small")

    # --- 1. LOGO A LA IZQUIERDA ---
    with col_logo:
        # Ruta del logo relativa a la raíz del proyecto
        logo_path = os.path.join(root_dir, "assets", "logo_LTC.png")
        
        if os.path.exists(logo_path):
            # Usamos use_container_width para que se adapte a la columna
            st.image(logo_path, width=180) 
        else:
            # Fallback si no encuentra la imagen
            st.markdown("### 🏢 **LTC**")
            st.caption("Logo no encontrado")

    # --- 2. MENÚ EN EL CENTRO ---
    with col_menu:
        selected = option_menu(
            menu_title=None, 
            options=["Dashboard", "Explorador", "Clasificador IA", "Simulador"],
            icons=["bar-chart-fill", "table", "robot", "graph-up-arrow"],
            menu_icon="cast",
            default_index=0,
            orientation="horizontal",
            styles={
                "container": {
                    "padding": "0!important", 
                    "background-color": "transparent", # Transparente para fusionarse
                    "margin": "0"
                },
                "icon": {"color": "#19AC86", "font-size": "14px"}, 
                "nav-link": {
                    "font-size": "15px", 
                    "text-align": "center", 
                    "margin": "0px 10px", # Espacio entre botones
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
    
    # --- 3. ESPACIO VACÍO A LA DERECHA (Para equilibrio) ---
    with col_spacer:
        st.write("") # Puedes poner aquí un icono de usuario o botón de logout en el futuro

# Línea separadora sutil
st.markdown("<div style='height: 2px; background-color: #f0f0f0; margin-bottom: 20px;'></div>", unsafe_allow_html=True)

# ==============================================================================
# ENRUTADOR DE VISTAS
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
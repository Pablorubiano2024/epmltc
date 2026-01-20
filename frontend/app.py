import sys
import os

# ==============================================================================
# 0. FIX DE IMPORTACIÓN (CRÍTICO)
# ==============================================================================
# Obtenemos la ruta de la carpeta donde está este archivo (frontend/)
current_dir = os.path.dirname(os.path.abspath(__file__))
# Obtenemos la ruta padre (epmltc/)
root_dir = os.path.dirname(current_dir)
# Agregamos la raíz al "path" de Python para que reconozca los imports
sys.path.append(root_dir)

# ==============================================================================
# IMPORTS
# ==============================================================================
import streamlit as st
from streamlit_option_menu import option_menu

# Ahora sí funcionan estos imports absolutos
from frontend.utils.enterprise_style import apply_enterprise_style, render_header
from frontend.views.dashboard import render_dashboard
from frontend.views.classifier import render_classifier
from frontend.views.projection import render_projection
from frontend.views.explorer import render_explorer

# ==============================================================================
# CONFIGURACIÓN ESTRUCTURAL
# ==============================================================================
# 1. Configuración de página (Debe ser lo primero de Streamlit)
st.set_page_config(page_title="EPM Enterprise", layout="wide", page_icon="🏢")

# 2. Aplicar CSS Global
apply_enterprise_style()

# 3. Menú de Navegación Superior
# Usamos un contenedor fluido para que ocupe todo el ancho
with st.container():
    selected = option_menu(
        menu_title=None,  # Ocultamos el título para que parezca navbar
        options=["Dashboard", "Explorador", "Clasificador IA", "Simulador"],
        icons=["bar-chart-fill", "table", "robot", "graph-up-arrow"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "#FFFFFF", "border-radius": "0", "margin": "0"},
            "icon": {"color": "#19AC86", "font-size": "14px"}, 
            "nav-link": {"font-size": "14px", "text-align": "center", "margin": "0px", "--hover-color": "#f0f2f6"},
            "nav-link-selected": {"background-color": "#122442", "color": "white", "font-weight": "600"},
        }
    )

# 4. Enrutador de Vistas (Carga el contenido según el menú)
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
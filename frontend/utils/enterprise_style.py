import streamlit as st

def apply_enterprise_style():
    """Aplica estilos CSS globales para simular un ERP (NetSuite/Oracle style)."""
    st.markdown("""
        <style>
            /* =========================================
               1. LIMPIEZA DE INTERFAZ (Modo App)
               ========================================= */
            [data-testid="stSidebar"] {display: none;}
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;} /* Oculta la barra de colores superior */

            /* =========================================
               2. FONDO Y FUENTES
               ========================================= */
            .stApp {
                background-color: #F4F6F9; /* Gris pálido empresarial */
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }

            /* =========================================
               3. AJUSTES DE LAYOUT
               ========================================= */
            .block-container {
                padding-top: 1.5rem !important;
                padding-left: 2rem !important;
                padding-right: 2rem !important;
                max-width: 100% !important;
            }

            /* --- FIX CRÍTICO: ALINEACIÓN VERTICAL DE COLUMNAS --- */
            /* Esto hace que el Logo y el Menú se centren verticalmente */
            [data-testid="column"] {
                display: flex;
                align-items: center;
                justify-content: center;
            }

            /* =========================================
               4. COMPONENTES: BOTONES
               ========================================= */
            div.stButton > button {
                background-color: #122442; /* Azul Navy */
                color: white;
                border-radius: 4px;
                border: none;
                padding: 0.5rem 1rem;
                font-weight: 600;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                transition: all 0.2s;
            }
            div.stButton > button:hover {
                background-color: #19AC86; /* Verde Corporativo */
                color: white;
                border-color: #19AC86;
                transform: translateY(-1px);
            }
            div.stButton > button:active {
                background-color: #122442;
                transform: translateY(0px);
            }

            /* =========================================
               5. COMPONENTES: CARDS (Tarjetas blancas)
               ========================================= */
            .ns-card {
                background-color: white;
                padding: 25px;
                border-radius: 6px;
                border-top: 3px solid #19AC86; /* Línea de acento superior */
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
                margin-bottom: 20px;
            }

            /* =========================================
               6. COMPONENTES: INPUTS
               ========================================= */
            .stTextInput input, .stSelectbox div, .stDateInput input, .stNumberInput input {
                border-radius: 4px;
                border: 1px solid #ced4da;
            }

            /* =========================================
               7. HEADER DE MÓDULO (Barra azul interna)
               ========================================= */
            .enterprise-header {
                background-color: #122442;
                color: white;
                padding: 12px 25px;
                margin-bottom: 25px;
                border-radius: 6px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .app-title { font-size: 1.1rem; font-weight: 700; letter-spacing: 1px; }
            .module-name { font-weight: 600; color: #19AC86; text-transform: uppercase; letter-spacing: 0.5px; }
            .user-info { font-size: 0.85rem; opacity: 0.9; background: rgba(255,255,255,0.1); padding: 5px 12px; border-radius: 20px; }
            
        </style>
    """, unsafe_allow_html=True)

def render_header(module_name="Inicio"):
    """Renderiza la barra de título del módulo actual."""
    st.markdown(f"""
        <div class="enterprise-header">
            <div class="app-title">🏢 EPM SYSTEM</div>
            <div class="module-name">{module_name}</div>
            <div class="user-info">👤 Admin User</div>
        </div>
    """, unsafe_allow_html=True)

def card_container(title=None):
    """Ayuda para crear contenedores visuales consistentes (Opcional)."""
    if title:
        st.markdown(f"<h5 style='color:#122442; margin-bottom:15px; font-weight:600;'>{title}</h5>", unsafe_allow_html=True)
    return st.container()
import streamlit as st

def apply_enterprise_style():
    """Aplica estilos CSS globales para simular un ERP."""
    st.markdown("""
        <style>
            /* 1. OCULTAR SIDEBAR NATIVO Y ELEMENTOS DE STREAMLIT */
            [data-testid="stSidebar"] {display: none;}
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;} /* Oculta la barra de colores de arriba de Streamlit */

            /* 2. FONDO Y FUENTES */
            .stApp {
                background-color: #F4F6F9;
                font-family: 'Segoe UI', Tahoma, sans-serif;
            }

            /* 3. AJUSTE DEL CONTENEDOR PRINCIPAL (Para que quepa el menú) */
            .block-container {
                padding-top: 1rem !important; /* Reducido para que el menú quede arriba */
                padding-left: 2rem !important;
                padding-right: 2rem !important;
                max-width: 100% !important;
            }

            /* 4. BOTONES */
            div.stButton > button {
                background-color: #122442;
                color: white;
                border-radius: 4px;
                border: none;
                padding: 0.5rem 1rem;
                font-weight: 600;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            div.stButton > button:hover {
                background-color: #19AC86;
                color: white;
                border-color: #19AC86;
            }

            /* 5. CARDS */
            .ns-card {
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                border-top: 3px solid #19AC86;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08);
                margin-bottom: 20px;
            }

            /* 6. HEADER DE MÓDULO (Ajustado para no tapar el menú) */
            .enterprise-header {
                background-color: #122442;
                color: white;
                padding: 10px 20px;
                margin-bottom: 20px;
                border-radius: 5px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .app-title { font-size: 1.1rem; font-weight: 700; letter-spacing: 1px; }
            .user-info { font-size: 0.8rem; opacity: 0.9; background: rgba(255,255,255,0.1); padding: 4px 10px; border-radius:15px; }
        </style>
    """, unsafe_allow_html=True)

def render_header(module_name="Inicio"):
    """Renderiza la barra de título del módulo actual."""
    st.markdown(f"""
        <div class="enterprise-header">
            <div class="app-title">🏢 EPM | LATAM TRADE CAPITAL</div>
            <div style="font-weight:600; color:#19AC86; text-transform: uppercase;">{module_name}</div>
            <div class="user-info">👤 Admin</div>
        </div>
    """, unsafe_allow_html=True)
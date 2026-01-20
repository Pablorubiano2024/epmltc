import streamlit as st
import base64

def load_css(logo_path="assets/logo_LTC.png"):
    """
    Inyecta CSS personalizado y configura el logo en el sidebar
    """
    
    # CSS Personalizado
    st.markdown("""
        <style>
            /* 1. Fondo general más limpio */
            .stApp {
                background-color: #F4F6F9;
            }
            
            /* 2. Tarjetas de Métricas (KPIs) Estilo 'Card' */
            div[data-testid="metric-container"] {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                color: #122442;
            }
            
            /* Título de la métrica */
            div[data-testid="metric-container"] label {
                color: #6c757d;
                font-size: 0.9rem;
            }
            
            /* Valor de la métrica */
            div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
                color: #122442;
                font-size: 1.8rem;
                font-weight: 700;
            }

            /* 3. Encabezados H1, H2, H3 con color corporativo */
            h1, h2, h3 {
                color: #122442 !important;
                font-family: 'Helvetica Neue', sans-serif;
            }
            
            /* 4. Barra Lateral más limpia */
            section[data-testid="stSidebar"] {
                box-shadow: 2px 0 5px rgba(0,0,0,0.05);
            }
            
            /* 5. Ajuste de botones */
            div.stButton > button {
                border-radius: 8px;
                font-weight: 600;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            /* 6. Contenedores de Gráficos (Fondo blanco) */
            .element-container iframe, .element-container .stPlotlyChart {
                background-color: #FFFFFF;
                border-radius: 10px;
                padding: 10px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }
        </style>
    """, unsafe_allow_html=True)

    # Inyectar Logo en el Sidebar (Parte Superior)
    try:
        st.sidebar.image(logo_path, use_container_width=True)
        st.sidebar.markdown("---") # Línea separadora
    except:
        st.sidebar.warning("⚠️ Logo no encontrado en assets/")
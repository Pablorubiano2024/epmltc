import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="Clasificador IA", layout="wide")

st.title("🤖 Clasificador Inteligente de Gastos")
st.markdown("""
Este módulo utiliza el modelo **Random Forest** entrenado con tus datos históricos para clasificar automáticamente 
los gastos que aún no tienen 'Grupo' o 'Subgrupo' asignado.
""")

# --- ESTADO DE LA SESIÓN (Para recordar datos entre clics) ---
if 'df_pending' not in st.session_state:
    st.session_state.df_pending = None
if 'df_predicted' not in st.session_state:
    st.session_state.df_predicted = None

# ==============================================================================
# PASO 1: CARGAR PENDIENTES
# ==============================================================================
st.subheader("1. Identificar Gastos sin Clasificar")

col_a, col_b = st.columns([1, 4])
with col_a:
    btn_load = st.button("📥 Cargar Pendientes")

if btn_load:
    with st.spinner("Buscando registros sin Grupo/Subgrupo..."):
        try:
            # LLAMADA A FASTAPI: Endpoint que busca WHERE grupo IS NULL
            response = requests.get("http://127.0.0.1:8000/api/v1/opex/pending-classification")
            
            if response.status_code == 200:
                data = response.json()
                df = pd.DataFrame(data)
                
                if not df.empty:
                    st.session_state.df_pending = df
                    st.session_state.df_predicted = None # Resetear predicciones anteriores
                    st.success(f"Se encontraron {len(df)} registros pendientes de clasificación.")
                else:
                    st.info("¡Todo está al día! No hay registros pendientes.")
            else:
                st.error("Error al consultar API.")
        except Exception as e:
            st.error(f"Error de conexión: {e}")

# Mostrar tabla si existe
if st.session_state.df_pending is not None and st.session_state.df_predicted is None:
    st.dataframe(st.session_state.df_pending.head(10), use_container_width=True)
    st.caption("Mostrando primeros 10 registros...")

# ==============================================================================
# PASO 2: EJECUTAR PREDICCIÓN (LA MAGIA)
# ==============================================================================
if st.session_state.df_pending is not None:
    st.divider()
    st.subheader("2. Ejecutar Motor de IA")
    
    col_x, col_y = st.columns([1, 4])
    with col_x:
        btn_predict = st.button("⚡ Clasificar con IA", type="primary")
    
    if btn_predict:
        with st.spinner("El modelo está analizando descripciones, cuentas y proveedores..."):
            try:
                # Preparamos el payload (los datos a enviar al backend)
                # Convertimos el DF a lista de diccionarios
                records_to_predict = st.session_state.df_pending.to_dict(orient='records')
                
                # LLAMADA A FASTAPI: Endpoint que carga los .pkl y predice
                response = requests.post("http://127.0.0.1:8000/api/v1/opex/predict", json=records_to_predict)
                
                if response.status_code == 200:
                    predicted_data = response.json()
                    st.session_state.df_predicted = pd.DataFrame(predicted_data)
                    st.success("¡Clasificación terminada!")
                else:
                    st.error(f"Error en el modelo: {response.text}")
                    
            except Exception as e:
                st.error(f"Error conectando con el modelo: {e}")

# ==============================================================================
# PASO 3: REVISIÓN Y RESULTADOS
# ==============================================================================
if st.session_state.df_predicted is not None:
    df_pred = st.session_state.df_predicted
    
    st.divider()
    st.subheader("3. Resultados y Confianza")
    
    # Métricas de confianza
    avg_conf = df_pred['confianza_grupo'].mean()
    st.metric("Confianza Promedio del Modelo", f"{avg_conf:.1f}%")
    
    # Colorear filas con baja confianza para llamar la atención
    def highlight_low_confidence(s):
        return ['background-color: #ffcccc' if v < 60 else '' for v in s]

    # Mostrar tabla con resultados
    st.dataframe(
        df_pred[['empresa', 'descripcion_gasto', 'cuenta_contable', 'grupo_predicho', 'subgrupo_predicho', 'confianza_grupo']],
        use_container_width=True,
        column_config={
            "confianza_grupo": st.column_config.ProgressColumn(
                "Nivel de Confianza",
                help="Qué tan seguro está el modelo",
                format="%.1f%%",
                min_value=0,
                max_value=100,
            ),
        }
    )
    
    # Gráfico de distribución de lo que encontró
    fig = px.pie(df_pred, names='grupo_predicho', title='Distribución de Gastos Clasificados')
    st.plotly_chart(fig, use_container_width=True)

    # Botón de Guardar (Esto enviaría un UPDATE a la BD)
    if st.button("💾 Guardar Clasificación en Base de Datos"):
        st.toast("Funcionalidad de guardado pendiente de implementar en Backend", icon="🚧")
        # Aquí llamarías a un endpoint PUT /api/v1/opex/update
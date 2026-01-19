import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="Clasificador IA", layout="wide")
st.title("🤖 Clasificador Inteligente de Gastos")

# API URL
API_URL = "http://127.0.0.1:8000/api/v1/opex"

# Session State
if 'df_pending' not in st.session_state: st.session_state.df_pending = None
if 'df_predicted' not in st.session_state: st.session_state.df_predicted = None

# ==============================================================================
# 1. CARGAR PENDIENTES
# ==============================================================================
st.subheader("1. Cargar Gastos Sin Clasificar")
limit = st.slider("Cantidad de registros a procesar", 10, 500, 50)

if st.button("📥 Buscar Pendientes"):
    with st.spinner("Consultando BD..."):
        try:
            res = requests.get(f"{API_URL}/pending-classification?limit={limit}")
            if res.status_code == 200:
                data = res.json()
                if data:
                    st.session_state.df_pending = pd.DataFrame(data)
                    st.session_state.df_predicted = None
                    st.success(f"Se cargaron {len(data)} registros pendientes.")
                else:
                    st.info("¡Todo limpio! No hay gastos pendientes.")
            else:
                st.error(f"Error API: {res.text}")
        except Exception as e:
            st.error(f"Error de conexión: {e}")

if st.session_state.df_pending is not None and st.session_state.df_predicted is None:
    st.dataframe(st.session_state.df_pending[['empresa','cuenta_contable','descripcion_gasto','valor']], use_container_width=True)

# ==============================================================================
# 2. PREDECIR
# ==============================================================================
if st.session_state.df_pending is not None:
    if st.button("⚡ Ejecutar Inteligencia Artificial", type="primary"):
        with st.spinner("El modelo está pensando..."):
            try:
                payload = st.session_state.df_pending.to_dict(orient='records')
                res = requests.post(f"{API_URL}/predict", json=payload)
                
                if res.status_code == 200:
                    st.session_state.df_predicted = pd.DataFrame(res.json())
                    st.success("¡Predicción completada!")
                else:
                    st.error(f"Error en predicción: {res.text}")
            except Exception as e:
                st.error(f"Error de conexión: {e}")

# ==============================================================================
# 3. REVISAR Y GUARDAR
# ==============================================================================
if st.session_state.df_predicted is not None:
    st.divider()
    st.subheader("3. Revisión y Guardado")
    st.info("💡 Puedes editar manualmente las celdas de 'Grupo' y 'Subgrupo' si la IA se equivocó.")
    
    df_pred = st.session_state.df_predicted.copy()
    
    # Preparar tabla para edición
    cols_order = ['empresa', 'descripcion_gasto', 'valor', 'grupo_predicho', 'subgrupo_predicho', 'confianza', 'id_transaccion']
    
    # DATA EDITOR: Permite corregir al usuario
    edited_df = st.data_editor(
        df_pred[cols_order],
        column_config={
            "grupo_predicho": st.column_config.TextColumn("Grupo (Editable)"),
            "subgrupo_predicho": st.column_config.TextColumn("Subgrupo (Editable)"),
            "confianza": st.column_config.ProgressColumn("Confianza IA", format="%.1f%%", min_value=0, max_value=100),
            "id_transaccion": st.column_config.NumberColumn("ID", disabled=True)
        },
        use_container_width=True,
        hide_index=True,
        num_rows="fixed"
    )
    
    col1, col2 = st.columns([1, 4])
    
    with col1:
        if st.button("💾 Guardar Cambios en BD", type="primary"):
            with st.spinner("Actualizando base de datos..."):
                try:
                    # Preparar Payload de actualización
                    update_payload = []
                    for _, row in edited_df.iterrows():
                        update_payload.append({
                            "id_transaccion": int(row['id_transaccion']),
                            "grupo": row['grupo_predicho'],
                            "subgrupo": row['subgrupo_predicho']
                        })
                    
                    # Enviar PUT
                    res = requests.put(f"{API_URL}/update-batch", json=update_payload)
                    
                    if res.status_code == 200:
                        st.balloons()
                        st.success(f"✅ ¡Éxito! Se actualizaron {len(update_payload)} registros.")
                        # Limpiar estado
                        st.session_state.df_pending = None
                        st.session_state.df_predicted = None
                    else:
                        st.error(f"Error guardando: {res.text}")
                        
                except Exception as e:
                    st.error(f"Error crítico: {e}")

    with col2:
        # Gráfico de resumen de lo que se va a guardar
        fig = px.histogram(edited_df, x='grupo_predicho', title="Resumen de Clasificación (Pre-Guardado)")
        st.plotly_chart(fig, use_container_width=True)
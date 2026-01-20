import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import time

# URL de la API
API_URL = "http://127.0.0.1:8000/api/v1/opex"

def render_classifier():
    """
    Renderiza la vista del Clasificador de IA.
    """
    # Inicializar estado si no existe
    if 'df_pending' not in st.session_state: st.session_state.df_pending = None
    if 'df_predicted' not in st.session_state: st.session_state.df_predicted = None

    # --- BARRA DE HERRAMIENTAS (FILTROS) ---
    st.markdown('<div class="ns-card">', unsafe_allow_html=True)
    st.markdown("##### ⚙️ Configuración de Procesamiento")
    
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.info("Este módulo busca gastos sin clasificar en la base de datos y aplica el modelo de IA para sugerir Grupo y Subgrupo.")
    with c2:
        limit = st.number_input("Límite de registros", min_value=10, max_value=1000, value=50)
    with c3:
        st.write("") # Espacio
        if st.button("📥 Buscar Pendientes", use_container_width=True):
            try:
                res = requests.get(f"{API_URL}/pending-classification?limit={limit}")
                if res.status_code == 200:
                    data = res.json()
                    if data:
                        st.session_state.df_pending = pd.DataFrame(data)
                        st.session_state.df_predicted = None
                        st.toast(f"Cargados {len(data)} registros", icon="✅")
                    else:
                        st.info("No hay registros pendientes.")
                        st.session_state.df_pending = None
                else:
                    st.error(f"Error API: {res.text}")
            except Exception as e: 
                st.error(f"Error de conexión: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

    # --- PASO 1: VISTA PREVIA (PENDIENTES) ---
    if st.session_state.df_pending is not None and st.session_state.df_predicted is None:
        st.markdown("##### 1. Datos encontrados (Crudos)")
        st.dataframe(
            st.session_state.df_pending[['empresa', 'cuenta_contable', 'descripcion_gasto', 'valor']], 
            use_container_width=True,
            hide_index=True
        )
        
        col_action, col_void = st.columns([1, 4])
        with col_action:
            if st.button("⚡ Ejecutar Inteligencia Artificial", type="primary"):
                with st.spinner("El modelo está analizando patrones..."):
                    try:
                        payload = st.session_state.df_pending.to_dict(orient='records')
                        res = requests.post(f"{API_URL}/predict", json=payload)
                        if res.status_code == 200:
                            st.session_state.df_predicted = pd.DataFrame(res.json())
                            st.rerun()
                        else:
                            st.error(f"Error en predicción: {res.text}")
                    except Exception as e:
                        st.error(f"Error técnico: {e}")

    # --- PASO 2: REVISIÓN Y GUARDADO ---
    if st.session_state.df_predicted is not None:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        st.markdown("##### 2. Resultados de la IA (Revisión)")
        st.caption("Edite las celdas si la IA se equivocó. Luego presione Guardar.")
        
        df_pred = st.session_state.df_predicted.copy()
        
        # Tabla Editable
        edited_df = st.data_editor(
            df_pred[['empresa', 'descripcion_gasto', 'valor', 'grupo_predicho', 'subgrupo_predicho', 'confianza', 'id_transaccion']],
            column_config={
                "grupo_predicho": st.column_config.TextColumn("Grupo", required=True),
                "subgrupo_predicho": st.column_config.TextColumn("Subgrupo", required=True),
                "confianza": st.column_config.ProgressColumn("Confianza IA", format="%.1f%%", min_value=0, max_value=100),
                "id_transaccion": st.column_config.NumberColumn("ID", disabled=True),
                "valor": st.column_config.NumberColumn("Monto", format="$%d")
            },
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            height=400
        )
        
        st.markdown("---")
        
        c_save, c_stats = st.columns([1, 2])
        
        with c_save:
            if st.button("💾 Aprobar y Guardar en BD", type="primary", use_container_width=True):
                with st.spinner("Guardando en base de datos..."):
                    try:
                        payload = []
                        for _, row in edited_df.iterrows():
                            payload.append({
                                "id_transaccion": int(row['id_transaccion']),
                                "grupo": row['grupo_predicho'],
                                "subgrupo": row['subgrupo_predicho']
                            })
                        
                        res = requests.put(f"{API_URL}/update-batch", json=payload)
                        
                        if res.status_code == 200:
                            st.success(f"✅ ¡Éxito! Se actualizaron {len(payload)} registros.")
                            st.session_state.df_pending = None
                            st.session_state.df_predicted = None
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(f"Error guardando: {res.text}")
                    except Exception as e: st.error(f"Error: {e}")
        
        with c_stats:
            # Pequeña gráfica de resumen
            fig = px.histogram(edited_df, x='grupo_predicho', title="Resumen de Clasificación", color_discrete_sequence=['#122442'])
            fig.update_layout(height=200, margin=dict(t=30, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import time

API_URL = "http://127.0.0.1:8000/api/v1/opex"

# --- FUNCIÓN AUXILIAR: TRAER CATEGORÍAS ---
def get_categories():
    try:
        res = requests.get(f"{API_URL}/categories")
        if res.status_code == 200:
            return res.json()
    except: pass
    return {"grupos": [], "subgrupos": []}

def render_classifier():
    if 'df_pending' not in st.session_state: st.session_state.df_pending = None
    if 'df_predicted' not in st.session_state: st.session_state.df_predicted = None

    # Cargar listas desplegables
    cats = get_categories()
    lista_grupos = cats.get("grupos", [])
    lista_subgrupos = cats.get("subgrupos", [])

    # TABS
    tab1, tab2 = st.tabs(["⚡ Clasificación Automática", "🛠️ Corrector Manual de Proveedores"])

    # ==============================================================================
    # TAB 1: CLASIFICACIÓN (No cambia mucho, solo visual)
    # ==============================================================================
    with tab1:
        st.markdown('<div class="ns-card">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: st.info("Busca gastos nuevos y aplica IA.")
        with c2: limit = st.number_input("Límite", 10, 2000, 100)
        with c3: 
            st.write("")
            if st.button("📥 Buscar Pendientes", use_container_width=True):
                try:
                    res = requests.get(f"{API_URL}/pending-classification?limit={limit}")
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.df_pending = pd.DataFrame(data) if data else None
                        if not data: st.success("Todo al día.")
                except: st.error("Error API")
        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.df_pending is not None and st.session_state.df_predicted is None:
            st.dataframe(st.session_state.df_pending[['empresa','descripcion_gasto','valor']], use_container_width=True)
            if st.button("⚡ Ejecutar IA", type="primary"):
                with st.spinner("Clasificando..."):
                    payload = st.session_state.df_pending.to_dict(orient='records')
                    res = requests.post(f"{API_URL}/predict", json=payload)
                    if res.status_code == 200:
                        st.session_state.df_predicted = pd.DataFrame(res.json())
                        st.rerun()

        if st.session_state.df_predicted is not None:
            st.markdown("##### Revisión")
            
            # Aquí también usamos Selectbox si quieres corregir antes de guardar
            edited_df = st.data_editor(
                st.session_state.df_predicted[['empresa','descripcion_gasto','valor','grupo_predicho','subgrupo_predicho','confianza','id_transaccion']],
                column_config={
                    "grupo_predicho": st.column_config.SelectboxColumn("Grupo", options=lista_grupos, required=True),
                    "subgrupo_predicho": st.column_config.SelectboxColumn("Subgrupo", options=lista_subgrupos, required=True),
                    "confianza": st.column_config.ProgressColumn("Confianza", format="%.1f%%"),
                    "id_transaccion": st.column_config.NumberColumn("ID", disabled=True)
                },
                use_container_width=True
            )
            
            if st.button("💾 Guardar Todo", type="primary"):
                with st.spinner("Guardando..."):
                    payload = []
                    for _, row in edited_df.iterrows():
                        payload.append({
                            "id_transaccion": int(row['id_transaccion']), 
                            "grupo": row['grupo_predicho'], 
                            "subgrupo": row['subgrupo_predicho']
                        })
                    requests.put(f"{API_URL}/update-batch", json=payload)
                    st.success("Guardado!"); st.session_state.df_pending=None; st.session_state.df_predicted=None; time.sleep(1); st.rerun()

    # ==============================================================================
    # TAB 2: CORRECTOR MANUAL (MEJORADO CON SELECTBOX)
    # ==============================================================================
    with tab2:
        st.markdown('<div class="ns-card"><h5>🔍 Corrector Maestro</h5>', unsafe_allow_html=True)
        
        col_search, _ = st.columns([3, 1])
        with col_search:
            prov_query = st.text_input("Buscar Proveedor (Nombre)", placeholder="Ej: Uber")
        
        if prov_query:
            with st.spinner(f"Buscando..."):
                try:
                    params = {
                        "start_date": "2024-01-01", "end_date": "2030-12-31",
                        "empresas": "CONIX,GFO,LTCP,LTCP2,NCPF,LEASING,AFI,LTC,NC SPA,NC L,NC SA,IN SA,INCOFIN LEASING,NC LEASING PERU,NC LEASING CHILE",
                        "proveedor": prov_query, "limit": 0
                    }
                    res = requests.get(f"{API_URL}/transactions", params=params)
                    
                    if res.status_code == 200:
                        df_res = pd.DataFrame(res.json())
                        if not df_res.empty:
                            df_res = df_res[df_res['nombre_tercero'].str.contains(prov_query, case=False, na=False)]
                            
                            # Agrupar
                            df_summary = df_res.groupby(['nombre_tercero', 'grupo', 'subgrupo']).size().reset_index(name='Registros')
                            
                            st.info(f"✅ {len(df_res)} transacciones encontradas.")
                            st.markdown("###### 👇 Modifique la clasificación en la tabla:")
                            
                            # --- EDITOR CON LISTAS DESPLEGABLES ---
                            edited_provs = st.data_editor(
                                df_summary,
                                column_config={
                                    "nombre_tercero": st.column_config.TextColumn("Proveedor", disabled=True),
                                    
                                    # DESPLEGABLES DINÁMICOS
                                    "grupo": st.column_config.SelectboxColumn(
                                        "Grupo (Seleccionar)", 
                                        options=lista_grupos, 
                                        required=True
                                    ),
                                    "subgrupo": st.column_config.SelectboxColumn(
                                        "Subgrupo (Seleccionar)", 
                                        options=lista_subgrupos, 
                                        required=True
                                    ),
                                    
                                    "Registros": st.column_config.NumberColumn("Cant.", disabled=True)
                                },
                                use_container_width=True,
                                hide_index=True,
                                key="editor_corrector"
                            )
                            
                            if st.button("💾 Aplicar Corrección Masiva", type="primary"):
                                with st.spinner("Actualizando histórico..."):
                                    count = 0
                                    for _, row in edited_provs.iterrows():
                                        # Enviamos el payload asegurando que vayan los datos
                                        payload = [{
                                            "nombre_tercero": row['nombre_tercero'],
                                            "grupo": row['grupo'],
                                            "subgrupo": row['subgrupo']
                                        }]
                                        
                                        r = requests.put(f"{API_URL}/update-provider-status", json=payload)
                                        if r.status_code == 200: count += r.json().get("updated_rows", 0)
                                    
                                    if count > 0:
                                        st.balloons()
                                        st.success(f"✅ ¡Éxito! Se corrigieron {count} registros y quedaron marcados como 'Manual'.")
                                        time.sleep(3)
                                        st.rerun()
                                    else:
                                        st.warning("No se encontraron registros para actualizar.")
                        else:
                            st.warning(f"No se encontraron resultados.")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)
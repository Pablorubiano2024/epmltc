import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date

API_URL = "http://127.0.0.1:8000/api/v1/opex/transactions"

def render_explorer():
    # --- 1. BARRA DE HERRAMIENTAS (FILTROS) ---
    st.markdown('<div class="ns-card">', unsafe_allow_html=True)
    st.markdown("##### 🔍 Filtros de Búsqueda")
    
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])
    
    with c1:
        start_date = st.date_input("Fecha Inicio", date(date.today().year, 1, 1))
    with c2:
        end_date = st.date_input("Fecha Fin", date.today())
    with c3:
        opciones_empresa = ['Todas', 'CONIX', 'GFO', 'LTCP', 'LTCP2', 'NCPF', 'LEASING', 'AFI', 'LTC', 'NC SPA', 'NC L', 'NC SA', 'IN SA', 'IN L']
        empresa_sel = st.multiselect("Empresas", options=opciones_empresa, default=['Todas'])
    with c4:
        cuenta_filter = st.text_input("Cuenta Contable", placeholder="Ej: 5105")
    with c5:
        st.write("")
        st.write("")
        buscar = st.button("🔎 Consultar", type="primary", use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    # --- 2. LÓGICA DE BÚSQUEDA ---
    if buscar:
        with st.spinner('Consultando base de datos unificada...'):
            try:
                if 'Todas' in empresa_sel or not empresa_sel:
                    empresas_str = "CONIX,GFO,LTCP,LTCP2,NCPF,LEASING,AFI,LTC,NC SPA,NC L,NC SA,IN SA,INCOFIN LEASING,NC LEASING PERU,NC LEASING CHILE"
                else:
                    empresas_str = ",".join(empresa_sel)

                params = {
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "empresas": empresas_str,
                    "cuenta": cuenta_filter if cuenta_filter else None
                }
                
                response = requests.get(API_URL, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    df = pd.DataFrame(data)
                    
                    if not df.empty:
                        # Asegurar que el valor es numérico (mantiene el signo negativo)
                        df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)
                        
                        # --- 3. RESULTADOS ---
                        st.markdown(f"##### Resultados: {len(df)} registros encontrados")
                        
                        k1, k2, k3 = st.columns(3)
                        k1.metric("Registros", len(df))
                        k2.metric("Monto Total (USD)", f"${df['valor'].sum():,.0f}")
                        k3.metric("Empresas", df['empresa'].nunique())
                        
                        st.divider()
                        
                        # Tabla en Pantalla (Formateada visualmente)
                        cols_order = ['fecha_transaccion', 'empresa', 'cuenta_contable', 'descripcion_gasto', 'nombre_tercero', 'valor', 'grupo', 'subgrupo']
                        cols_existentes = [c for c in cols_order if c in df.columns]
                        
                        st.dataframe(
                            df[cols_existentes],
                            use_container_width=True,
                            height=500,
                            column_config={
                                "valor": st.column_config.NumberColumn("Valor", format="$%d"), # Solo visual
                                "fecha_transaccion": st.column_config.DateColumn("Fecha"),
                                "descripcion_gasto": st.column_config.TextColumn("Descripción", width="medium"),
                            },
                            hide_index=True
                        )
                        
                        # Descarga CSV (Datos reales con signo)
                        # utf-8-sig es CRÍTICO para que Excel abra bien las tildes y signos
                        csv = df[cols_existentes].to_csv(index=False).encode('utf-8-sig')
                        
                        st.download_button(
                            "⬇️ Descargar Reporte (CSV Compatible Excel)",
                            data=csv,
                            file_name=f"reporte_opex_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                        )
                    else:
                        st.warning("No se encontraron registros con esos criterios.")
                else:
                    st.error(f"Error del servidor: {response.status_code}")

            except Exception as e:
                st.error(f"Error de conexión: {e}")
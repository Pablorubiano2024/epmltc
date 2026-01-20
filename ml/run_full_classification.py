import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import sys
import os
import joblib
import time
import io

# ==============================================================================
# 0. CONFIGURACIÓN SSL (Por si acaso)
# ==============================================================================
if not os.environ.get("OPENSSL_CONF"):
    ssl_path = os.path.join(os.getcwd(), "openssl_legacy.cnf")
    if os.path.exists(ssl_path):
        os.environ["OPENSSL_CONF"] = ssl_path

print("🚀 INICIANDO CLASIFICACIÓN MASIVA CON IA...")

# ==============================================================================
# 1. CONEXIÓN Y CONFIGURACIÓN
# ==============================================================================
def get_env(var):
    val = os.getenv(var)
    if not val:
        print(f"❌ Falta variable: {var}"); sys.exit(1)
    return val

PG_HOST, PG_DB = get_env("PG_HOST"), get_env("PG_DB")
PG_USER, PG_PASS = get_env("PG_USER"), get_env("PG_PASS")

url_pg = f"postgresql://{PG_USER}:{quote_plus(PG_PASS)}@{PG_HOST}:5432/{PG_DB}"
# Usamos autocommit para los ALTER TABLE
engine = create_engine(url_pg, isolation_level="AUTOCOMMIT") 

# Rutas de Modelos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "backend", "ml_models")

SCHEMA = "control_gestion"
TABLA = "libros_diarios_consolidados"
CHUNK_SIZE = 50000

# ==============================================================================
# 2. CARGAR MODELOS
# ==============================================================================
print(f"🧠 Cargando modelos desde {MODEL_DIR}...")
try:
    model_grupo = joblib.load(os.path.join(MODEL_DIR, "modelo_grupo.pkl"))
    model_subgrupo = joblib.load(os.path.join(MODEL_DIR, "modelo_subgrupo.pkl"))
    print("✅ Modelos cargados.")
except Exception as e:
    print(f"❌ Error cargando modelos: {e}")
    sys.exit(1)

# ==============================================================================
# 2.5 🛠️ BLINDAJE DE TABLA (Crear columnas si no existen)
# ==============================================================================
print("🛠️ Verificando estructura de la base de datos...")
try:
    with engine.connect() as conn:
        # Aseguramos que existan las columnas de IA y el ID único
        conn.execute(text(f'ALTER TABLE "{SCHEMA}"."{TABLA}" ADD COLUMN IF NOT EXISTS id_transaccion SERIAL PRIMARY KEY'))
        conn.execute(text(f'ALTER TABLE "{SCHEMA}"."{TABLA}" ADD COLUMN IF NOT EXISTS grupo TEXT'))
        conn.execute(text(f'ALTER TABLE "{SCHEMA}"."{TABLA}" ADD COLUMN IF NOT EXISTS subgrupo TEXT'))
    print("✅ Estructura validada correctamente.")
except Exception as e:
    print(f"⚠️ Nota: Error validando columnas (quizás ya existen): {e}")

# Cambiamos el engine a modo normal (sin autocommit) para el resto del proceso
engine = create_engine(url_pg)

# ==============================================================================
# 3. VERIFICAR PENDIENTES
# ==============================================================================
print("🔍 Buscando registros sin clasificar...")
try:
    with engine.connect() as conn:
        count = conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.{TABLA} WHERE grupo IS NULL")).scalar()
        print(f"📊 Registros pendientes: {count}")

    if count == 0:
        print("🎉 Todo está clasificado. No hay nada que hacer.")
        sys.exit(0)
except Exception as e:
    print(f"❌ Error fatal consultando BD: {e}")
    sys.exit(1)

# ==============================================================================
# 4. PROCESO DE CLASIFICACIÓN Y UPDATE MASIVO
# ==============================================================================
query = f"""
    SELECT id_transaccion, cuenta_contable, id_proveedor, descripcion_gasto 
    FROM {SCHEMA}.{TABLA}
    WHERE grupo IS NULL
"""

total_procesado = 0
start_time = time.time()

# Iteramos por lotes
for chunk in pd.read_sql(query, engine, chunksize=CHUNK_SIZE):
    if chunk.empty: break
    
    # A. Preprocesamiento
    chunk['descripcion_gasto'] = chunk['descripcion_gasto'].fillna('')
    chunk['id_proveedor'] = chunk['id_proveedor'].fillna('')
    chunk['cuenta_contable'] = chunk['cuenta_contable'].fillna('')
    
    X_input = (
        chunk['cuenta_contable'].astype(str) + " " +
        chunk['id_proveedor'].astype(str) + " " +
        chunk['descripcion_gasto'].astype(str)
    ).str.lower()
    
    # B. Predicción
    chunk['grupo'] = model_grupo.predict(X_input)
    chunk['subgrupo'] = model_subgrupo.predict(X_input)
    
    df_update = chunk[['id_transaccion', 'grupo', 'subgrupo']]
    
    # C. Update Masivo (Tabla Temporal)
    temp_table = "temp_clasificacion_updates"
    
    try:
        with engine.begin() as conn:
            df_update.head(0).to_sql(temp_table, conn, schema=SCHEMA, if_exists='replace', index=False)
            
            raw_conn = conn.connection
            with raw_conn.cursor() as cursor:
                output = io.StringIO()
                df_update.to_csv(output, sep='\t', header=False, index=False)
                output.seek(0)
                cursor.copy_expert(f"COPY {SCHEMA}.{temp_table} FROM STDIN", output)
            
            sql_update = text(f"""
                UPDATE {SCHEMA}.{TABLA} AS main
                SET grupo = temp.grupo,
                    subgrupo = temp.subgrupo
                FROM {SCHEMA}.{temp_table} AS temp
                WHERE main.id_transaccion = temp.id_transaccion
            """)
            conn.execute(sql_update)
            conn.execute(text(f"DROP TABLE IF EXISTS {SCHEMA}.{temp_table}"))
            
        total_procesado += len(chunk)
        sys.stdout.write(f"\r   ⏳ Procesado: {total_procesado} / {count} registros...")
        sys.stdout.flush()
        
    except Exception as e:
        print(f"\n   ❌ Error en el lote: {e}")

duration = time.time() - start_time
print(f"\n\n✅ CLASIFICACIÓN FINALIZADA.")
print(f"⏱️ Tiempo: {duration:.1f} seg | 📊 Total: {total_procesado}")
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
# 0. CONFIGURACIÓN SSL (Por compatibilidad de entorno)
# ==============================================================================
if not os.environ.get("OPENSSL_CONF"):
    ssl_path = os.path.join(os.getcwd(), "openssl_legacy.cnf")
    if os.path.exists(ssl_path):
        os.environ["OPENSSL_CONF"] = ssl_path

print("🚀 INICIANDO CLASIFICACIÓN Y UNIFICACIÓN (CON PROTECCIÓN MANUAL)...")

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

# Usamos autocommit para operaciones DDL (Alter table)
url_pg = f"postgresql://{PG_USER}:{quote_plus(PG_PASS)}@{PG_HOST}:5432/{PG_DB}"
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
# 3. BLINDAJE DE ESTRUCTURA (AUTO-REPARACIÓN)
# ==============================================================================
print("🛠️ Verificando estructura de la base de datos...")
try:
    with engine.connect() as conn:
        conn.execute(text(f'ALTER TABLE "{SCHEMA}"."{TABLA}" ADD COLUMN IF NOT EXISTS id_transaccion SERIAL PRIMARY KEY'))
        conn.execute(text(f'ALTER TABLE "{SCHEMA}"."{TABLA}" ADD COLUMN IF NOT EXISTS grupo TEXT'))
        conn.execute(text(f'ALTER TABLE "{SCHEMA}"."{TABLA}" ADD COLUMN IF NOT EXISTS subgrupo TEXT'))
        # Nueva columna para proteger cambios manuales
        conn.execute(text(f'ALTER TABLE "{SCHEMA}"."{TABLA}" ADD COLUMN IF NOT EXISTS clasificacion_manual BOOLEAN DEFAULT FALSE'))
    print("✅ Estructura validada.")
except Exception as e:
    print(f"⚠️ Nota estructura: {e}")

# Cambiamos engine a modo estándar para transacciones
engine = create_engine(url_pg)

# ==============================================================================
# 4. CLASIFICACIÓN DE PENDIENTES
# ==============================================================================
print("🔍 Buscando registros pendientes...")
with engine.connect() as conn:
    # Solo contamos los que NO tienen grupo Y NO son manuales
    sql_count = text(f"""
        SELECT count(*) FROM {SCHEMA}.{TABLA} 
        WHERE (grupo IS NULL OR grupo = '') 
        AND (clasificacion_manual IS FALSE OR clasificacion_manual IS NULL)
    """)
    count = conn.execute(sql_count).scalar()
    
if count > 0:
    print(f"📊 Clasificando {count} registros...")
    
    query = f"""
        SELECT id_transaccion, cuenta_contable, id_proveedor, descripcion_gasto 
        FROM {SCHEMA}.{TABLA}
        WHERE (grupo IS NULL OR grupo = '')
        AND (clasificacion_manual IS FALSE OR clasificacion_manual IS NULL)
    """
    
    total_procesado = 0
    start_time = time.time()
    
    for chunk in pd.read_sql(query, engine, chunksize=CHUNK_SIZE):
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
        
        # C. Update Masivo
        df_up = chunk[['id_transaccion', 'grupo', 'subgrupo']]
        temp_table = "temp_clasif_update"
        
        try:
            with engine.begin() as conn:
                # Tabla temporal
                df_up.head(0).to_sql(temp_table, conn, schema=SCHEMA, if_exists='replace', index=False)
                
                # Copy rápido
                raw_conn = conn.connection
                with raw_conn.cursor() as cursor:
                    output = io.StringIO()
                    df_up.to_csv(output, sep='\t', header=False, index=False)
                    output.seek(0)
                    cursor.copy_expert(f"COPY {SCHEMA}.{temp_table} FROM STDIN", output)
                
                # Update final
                conn.execute(text(f"""
                    UPDATE {SCHEMA}.{TABLA} AS m 
                    SET grupo = t.grupo, subgrupo = t.subgrupo 
                    FROM {SCHEMA}.{temp_table} t 
                    WHERE m.id_transaccion = t.id_transaccion
                """))
                conn.execute(text(f"DROP TABLE IF EXISTS {SCHEMA}.{temp_table}"))
                
            total_procesado += len(chunk)
            sys.stdout.write(f"\r   ⏳ Procesado: {total_procesado} / {count}...")
            sys.stdout.flush()

        except Exception as e:
            print(f"\n❌ Error en lote: {e}")
    
    print(f"\n✅ Clasificación terminada en {time.time() - start_time:.1f} seg.")

else:
    print("🎉 Nada pendiente de clasificar.")

# ==============================================================================
# 5. UNIFICACIÓN DE CONSISTENCIA (POST-PROCESO)
# ==============================================================================
print("\n🧹 Unificando categorías por Proveedor (Corrección de Coherencia)...")
print("   (Esto asegura que un mismo proveedor siempre tenga el mismo Grupo, salvo excepciones manuales)")

try:
    with engine.begin() as conn:
        # Lógica: Calcula la Moda (Categoría más frecuente) por proveedor y actualiza sus registros
        # PERO: Respeta si clasificacion_manual = TRUE
        sql_unify = text(f"""
            WITH Moda AS (
                SELECT 
                    nombre_tercero,
                    MODE() WITHIN GROUP (ORDER BY grupo) as grupo_comun,
                    MODE() WITHIN GROUP (ORDER BY subgrupo) as subgrupo_comun
                FROM {SCHEMA}.{TABLA}
                WHERE grupo IS NOT NULL AND nombre_tercero <> '' AND nombre_tercero <> 'SIN_ID'
                GROUP BY nombre_tercero
            )
            UPDATE {SCHEMA}.{TABLA} t
            SET grupo = m.grupo_comun,
                subgrupo = m.subgrupo_comun
            FROM Moda m
            WHERE t.nombre_tercero = m.nombre_tercero
            AND (t.grupo <> m.grupo_comun OR t.subgrupo <> m.subgrupo_comun)
            AND (t.clasificacion_manual IS FALSE OR t.clasificacion_manual IS NULL);
        """)
        res = conn.execute(sql_unify)
        print(f"   ✅ Se unificaron {res.rowcount} registros inconsistentes.")

except Exception as e:
    print(f"   ⚠️ Error unificación: {e}")

print("\n🎉 PROCESO FINALIZADO.")
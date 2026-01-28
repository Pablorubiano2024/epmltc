import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from pandas.tseries.offsets import MonthEnd
import sys
import os
import time

# ==============================================================================
# 0. CONFIGURACIÓN SSL (PARCHE PARA SERVIDORES ANTIGUOS)
# ==============================================================================
if not os.environ.get("OPENSSL_CONF"):
    print("🔓 Configurando parche SSL Legacy...")
    ssl_conf_path = os.path.join(os.getcwd(), "openssl_legacy.cnf")
    with open(ssl_conf_path, "w") as f:
        f.write("openssl_conf = openssl_init\n[openssl_init]\nssl_conf = ssl_sect\n[ssl_sect]\nsystem_default = system_default_sect\n[system_default_sect]\nCipherString = DEFAULT:@SECLEVEL=0")
    os.environ["OPENSSL_CONF"] = ssl_conf_path

print("🚀 INICIANDO ETL OPEX (FULL LOAD + ESTRUCTURA COMPLETA)...")

# ==============================================================================
# 1. CARGA DE VARIABLES DE ENTORNO
# ==============================================================================
def get_env(var):
    val = os.getenv(var)
    if not val:
        print(f"❌ Falta variable: {var}"); sys.exit(1)
    return val

# PostgreSQL
PG_HOST, PG_DB = get_env("PG_HOST"), get_env("PG_DB")
PG_USER, PG_PASS = get_env("PG_USER"), get_env("PG_PASS")

# SQL Servers
SRV_AFI_HOST = os.getenv("SQL_AFI_HOST", "35.169.137.82")
SRV_AFI_USER, SRV_AFI_PASS = os.getenv("SQL_AFI_USER", "usr_factor"), os.getenv("SQL_AFI_PASS", "*640hcm1")

SQL_GEN_HOST, SQL_GEN_USER, SQL_GEN_PASS = get_env("SQL_GEN_HOST"), get_env("SQL_GEN_USER"), get_env("SQL_GEN_PASS")
SQL_INSA_HOST, SQL_INSA_PORT = get_env("SQL_INSA_HOST"), os.getenv("SQL_INSA_PORT", "1435")
SQL_INSA_DB, SQL_INSA_USER, SQL_INSA_PASS = get_env("SQL_INSA_DB"), get_env("SQL_INSA_USER"), get_env("SQL_INSA_PASS")

# LEASING: Puerto Fijo 59043
SQL_INL_IP   = "182.160.26.74"
SQL_INL_PORT = "59043"
SQL_INL_HOST = f"{SQL_INL_IP},{SQL_INL_PORT}"
SQL_INL_DB   = get_env("SQL_INL_DB")
SQL_INL_USER, SQL_INL_PASS = get_env("SQL_INL_USER"), get_env("SQL_INL_PASS")

DRIVER = "ODBC Driver 17 for SQL Server"
PARAMS = f"?driver={quote_plus(DRIVER)}&Encrypt=no&TrustServerCertificate=yes&LoginTimeout=180"

# ==============================================================================
# 2. LIMPIEZA DE BASE DE DATOS (DROP TABLE)
# ==============================================================================
SCHEMA_DEST = "control_gestion"
TABLA_DEST  = "libros_diarios_consolidados"
url_pg = f"postgresql://{PG_USER}:{quote_plus(PG_PASS)}@{PG_HOST}:5432/{PG_DB}"
engine_pg = create_engine(url_pg, pool_pre_ping=True)

print("\n🧹 LIMPIEZA TOTAL: Borrando tabla destino...")
try:
    with engine_pg.connect() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{SCHEMA_DEST}"."{TABLA_DEST}"'))
        conn.commit()
    print("   ✅ Tabla eliminada. Se creará desde cero.")
except Exception as e:
    print(f"   ⚠️ Error borrando tabla: {e}")
    sys.exit(1)

# ==============================================================================
# 3. FILTROS SQL (WHERE)
# ==============================================================================

# Filtro Genérico PostgreSQL (Para todo menos GFO)
def get_pg_filter_general(col_fecha, col_cuenta):
    return f"""
    AND {col_fecha}::date >= '2024-01-01' 
    AND ({col_cuenta}::text LIKE '31%%' OR {col_cuenta}::text LIKE '32%%' OR {col_cuenta}::text LIKE '42%%')
    """

# Filtro Genérico SQL Server (Para todo menos Leasing)
FILTER_SQL_SRV_GENERAL = """
AND DC.Com_Periodo >= '202401'
AND (DC.Cta_Codigo LIKE '31%' OR DC.Cta_Codigo LIKE '32%' OR DC.Cta_Codigo LIKE '42%')
"""

# Excepciones GFO
excepciones_gfo = "('52991005', '53050503', '53051505', '53052005', '53052015')"

# ==============================================================================
# 4. QUERIES DE EXTRACCIÓN
# ==============================================================================

# --- A. PostgreSQL (Histórico) ---
q_pg = {
    # GFO: Lógica Débito/Crédito + Cuentas 5 + Excepciones
    'GFO': f"""
        SELECT 'GFO' as empresa, 
               fecha_corte, 
               fecha_docto::text as fecha_transaccion, 
               cuenta as cuenta_contable, 
               tercero as id_proveedor, 
               nombre_razon_social as nombre_tercero, 
               CONCAT_WS(' ', detalle, c_o_descripcion, cuenta_descripcion, c_costo_descripcion) as descripcion_gasto, 
               CAST(
                   CASE 
                       WHEN d_c = 'D' THEN valor_l2 
                       WHEN d_c = 'C' THEN -valor_l2 
                       ELSE 0 
                   END 
               AS NUMERIC) as valor 
        FROM control_gestion.libros_diarios_gfo 
        WHERE 1=1 
          AND fecha_docto::date >= '2024-01-01'
          AND cuenta::text LIKE '5%%'
          AND cuenta::text NOT IN {excepciones_gfo}
    """,

    # CONIX: Signo Invertido
    'CONIX': f"""
        SELECT 'CONIX' as empresa, 
               fecha_corte, 
               d_fecha_documento::text as fecha_transaccion, 
               k_sc_codigo_cuenta as cuenta_contable, 
               n_nit as id_proveedor, 
               sc_nombre as nombre_tercero, 
               CONCAT_WS(' ', sc_nombre_cuenta, sv_observaciones, sc_nombre_centro_costo) as descripcion_gasto, 
               (n_valor * -1) as valor 
        FROM control_gestion.libros_diarios_conix 
        WHERE 1=1 {get_pg_filter_general('d_fecha_documento', 'k_sc_codigo_cuenta')}
    """,
    
    'LTCP': f"""SELECT 'LTCP' as empresa, fecha_corte, "FEC DOC"::text as fecha_transaccion, "CUENTA" as cuenta_contable, "ANEXO" as id_proveedor, NULL as nombre_tercero, CONCAT_WS(' ', "CONCEPTO", "C COSTO") as descripcion_gasto, (COALESCE("DEBE  - MN", 0) - COALESCE("HABER - MN", 0)) as valor FROM control_gestion.libros_diarios_ltcp WHERE 1=1 {get_pg_filter_general('"FEC DOC"', '"CUENTA"')}""",
    'LTCP2': f"""SELECT 'LTCP2' as empresa, fecha_corte, "FEC DOC"::text as fecha_transaccion, "CUENTA" as cuenta_contable, "ANEXO" as id_proveedor, NULL as nombre_tercero, CONCAT_WS(' ', "CONCEPTO", "C COSTO") as descripcion_gasto, (COALESCE("DEBE  - MN", 0) - COALESCE("HABER - MN", 0)) as valor FROM control_gestion.libros_diarios_ltcp2 WHERE 1=1 {get_pg_filter_general('"FEC DOC"', '"CUENTA"')}""",
    'NCPF': f"""SELECT 'NCPF' as empresa, fecha_corte, "FEC DOC"::text as fecha_transaccion, "CUENTA" as cuenta_contable, "ANEXO" as id_proveedor, NULL as nombre_tercero, CONCAT_WS(' ', "CONCEPTO", "C COSTO") as descripcion_gasto, (COALESCE("DEBE  - MN", 0) - COALESCE("HABER - MN", 0)) as valor FROM control_gestion.libros_diarios_ncpf WHERE 1=1 {get_pg_filter_general('"FEC DOC"', '"CUENTA"')}""",
    'NC LEASING PERU': f"""SELECT 'NC LEASING PERU' as empresa, fecha_corte, "fec_doc"::text as fecha_transaccion, "cuenta" as cuenta_contable, "anexo" as id_proveedor, NULL as nombre_tercero, CONCAT_WS(' ', "concepto", "centro_costo") as descripcion_gasto, (COALESCE("debe_mn", 0) - COALESCE("haber_mn", 0)) as valor FROM control_gestion.libros_diarios_nc_leasing WHERE 1=1 {get_pg_filter_general('"fec_doc"', 'cuenta')}"""
}

# --- B. SQL Server ---
f_afi = "CAST(LEFT(DC.Com_Periodo, 4) + '-' + SUBSTRING(DC.Com_Periodo, 5, 2) + '-01' AS DATE)"
sql_afi = f"""SELECT 'AFI' as empresa, CONVERT(VARCHAR(10), {f_afi}, 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM dbo.Detalle_Comprobante DC LEFT JOIN dbo.Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN dbo.Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN dbo.Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo WHERE DC.Com_Numero IS NOT NULL {FILTER_SQL_SRV_GENERAL}"""

sql_ltc = f"""SELECT 'LTC' as empresa, CONVERT(VARCHAR(10), {f_afi}, 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM dbo.Detalle_Comprobante DC LEFT JOIN dbo.Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN dbo.Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN dbo.Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo WHERE DC.Com_Numero IS NOT NULL {FILTER_SQL_SRV_GENERAL}"""

f_nc = "CAST(SUBSTRING(DC.Com_Periodo, 1, 4) + '-' + SUBSTRING(DC.Com_Periodo, 5, 2) + '-01' AS DATE)"
sql_nc_spa = f"""SELECT 'NC SPA' as empresa, CONVERT(VARCHAR(10), {f_nc}, 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM Detalle_Comprobante DC LEFT JOIN Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo LEFT JOIN Comprobante C ON DC.Com_Numero = C.Com_Numero AND DC.Com_Periodo = C.Com_Periodo WHERE C.Com_Estado <> 'A' {FILTER_SQL_SRV_GENERAL}"""

sql_nc_l = f"""SELECT 'NC LEASING CHILE' as empresa, CONVERT(VARCHAR(10), {f_nc}, 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM Detalle_Comprobante DC LEFT JOIN Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo LEFT JOIN Comprobante C ON DC.Com_Numero = C.Com_Numero AND DC.Com_Periodo = C.Com_Periodo WHERE C.Com_Estado <> 'A' {FILTER_SQL_SRV_GENERAL}"""

sql_nc_sa = f"""SELECT 'NC SA' as empresa, CONVERT(VARCHAR(10), {f_nc}, 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM Detalle_Comprobante DC LEFT JOIN Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo LEFT JOIN Comprobante C ON DC.Com_Numero = C.Com_Numero AND DC.Com_Periodo = C.Com_Periodo WHERE C.Com_Estado <> 'A' {FILTER_SQL_SRV_GENERAL}"""

f_insa = "CAST(SUBSTRING(DC.Com_Periodo, 1, 4) + '-' + SUBSTRING(DC.Com_Periodo, 5, 2) + '-01' AS DATE)"
sql_in_sa = f"""SELECT 'IN SA' as empresa, CONVERT(VARCHAR(10), {f_insa}, 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM Detalle_Comprobante DC LEFT JOIN Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo LEFT JOIN Comprobante C ON DC.Com_Numero = C.Com_Numero AND DC.Com_Periodo = C.Com_Periodo WHERE C.Com_Estado <> 'A' {FILTER_SQL_SRV_GENERAL}"""

# INCOFIN LEASING (SIN FILTRO DE CUENTAS, TRAE TODO PARA EVITAR ERRORES, LUEGO SE FILTRA EN DASHBOARD)
sql_in_l = """
SELECT 'INCOFIN LEASING' as empresa, 
       CONVERT(VARCHAR(10), CAST(c.fecha_comp AS DATE), 23) as fecha_transaccion, 
       cd.cod_cuenta as cuenta_contable, 
       ISNULL(CAST(cd.con_analisis1 AS VARCHAR), '') + '-' + ISNULL(CAST(cd.dv_con_analisis1 AS VARCHAR), '') as id_proveedor,
       NULL as nombre_tercero, 
       ISNULL(cd.glosa_det_comp,'') + ' ' + ISNULL(cu.descripcion,'') as descripcion_gasto, 
       (cd.mto_deb_$ - cd.mto_hab_$) as valor 
FROM dbo.t_comprobante_detalle cd 
INNER JOIN dbo.t_comprobante c ON cd.num_comp = c.num_comp 
LEFT JOIN dbo.t_cuentas cu ON cd.cod_cuenta = cu.cod_cuenta 
WHERE c.fecha_comp >= '2024-01-01'
  AND (cd.cod_cuenta LIKE '31%' OR cd.cod_cuenta LIKE '32%' OR cd.cod_cuenta LIKE '42%')
"""

# ==============================================================================
# 5. CARGA
# ==============================================================================
def cargar_chunk_a_postgres(df_chunk):
    if df_chunk.empty: return 0
    # Transformaciones
    if 'fecha_corte' not in df_chunk.columns:
        df_chunk['fecha_transaccion'] = pd.to_datetime(df_chunk['fecha_transaccion'], errors='coerce')
        df_chunk['fecha_corte'] = df_chunk['fecha_transaccion'] + MonthEnd(0)
    else:
        df_chunk['fecha_corte'] = pd.to_datetime(df_chunk['fecha_corte'])
        df_chunk['fecha_transaccion'] = df_chunk['fecha_transaccion'].astype(str)

    df_chunk['descripcion_gasto'] = df_chunk['descripcion_gasto'].astype(str).str.slice(0, 500)
    df_chunk['id_proveedor'] = df_chunk['id_proveedor'].fillna('SIN_ID').astype(str)
    df_chunk['nombre_tercero'] = df_chunk['nombre_tercero'].fillna('').astype(str)
    df_chunk['valor'] = pd.to_numeric(df_chunk['valor'], errors='coerce').fillna(0)

    try:
        df_chunk.to_sql(TABLA_DEST, con=engine_pg, schema=SCHEMA_DEST, if_exists='append', index=False, method='multi', chunksize=2000)
        return len(df_chunk)
    except Exception as e:
        print(f"      ❌ Error DB: {e}")
        return 0

total = 0
def procesar(queries, host, user, pw, db_map=None, spec_db=None, port=None):
    global total
    srv = f"{host},{port}" if port else host
    targets = {spec_db: queries} if spec_db else (db_map or {})
    
    for db, q in targets.items():
        print(f"   ► [{db}]...", end=" ", flush=True)
        try:
            url = f"mssql+pyodbc://{user}:{quote_plus(pw)}@{srv}/{db}{PARAMS}"
            eng = create_engine(url, connect_args={'timeout': 180})
            rows = 0
            with eng.connect().execution_options(stream_results=True) as c:
                for df in pd.read_sql(q, c, chunksize=25000):
                    rows += cargar_chunk_a_postgres(df)
                    sys.stdout.write("█"); sys.stdout.flush()
            total += rows
            print(f" ✅ {rows}")
            time.sleep(2)
        except Exception as e: print(f" ❌ {e}")

print("\n🔄 MIGRANDO DATOS...")

# PG
print("   [PostgreSQL] Procesando...")
try:
    with engine_pg.connect() as conn_pg:
        for nombre_empresa, query in q_pg.items():
            print(f"      - {nombre_empresa}...", end=" ", flush=True)
            try:
                for df in pd.read_sql(text(query), conn_pg, chunksize=50000):
                    total += cargar_chunk_a_postgres(df)
                    sys.stdout.write("█"); sys.stdout.flush()
                print(" ✅")
            except Exception as e:
                print(f"❌ Error: {e}")
except Exception as e: print(f"   ⚠️ Error General PG: {e}")

# SQLs
procesar(None, SRV_AFI_HOST, SRV_AFI_USER, SRV_AFI_PASS, db_map={'FirContabAdm': sql_afi, 'FirContab': sql_ltc})
procesar(None, SQL_GEN_HOST, SQL_GEN_USER, SQL_GEN_PASS, db_map={'ncscontab_cob': sql_nc_spa, 'ncscontab_lea': sql_nc_l, 'ncsContab': sql_nc_sa})
procesar(sql_in_sa, SQL_INSA_HOST, SQL_INSA_USER, SQL_INSA_PASS, port=SQL_INSA_PORT, spec_db=SQL_INSA_DB)
procesar(sql_in_l, SQL_INL_IP, SQL_INL_USER, SQL_INL_PASS, port=SQL_INL_PORT, spec_db=SQL_INL_DB)

print(f"\n🎉 FIN. Nuevos registros: {total}")
try:
    with engine_pg.connect() as conn:
        conn.execute(text(f'CREATE INDEX IF NOT EXISTS idx_fc_consol ON "{SCHEMA_DEST}"."{TABLA_DEST}" (fecha_corte)'))
        conn.execute(text(f'CREATE INDEX IF NOT EXISTS idx_cta_consol ON "{SCHEMA_DEST}"."{TABLA_DEST}" (cuenta_contable)'))
        conn.commit()
    print("✅ Índices reconstruidos.")
except: pass

# ==============================================================================
# 6. ESTRUCTURA FINAL (COLUMNAS DE IA Y GESTIÓN)
# ==============================================================================
print("🔨 Ajustando estructura final...")
try:
    with engine_pg.connect() as conn:
        conn.execute(text(f'ALTER TABLE "{SCHEMA_DEST}"."{TABLA_DEST}" ADD COLUMN IF NOT EXISTS id_transaccion SERIAL PRIMARY KEY'))
        conn.execute(text(f'ALTER TABLE "{SCHEMA_DEST}"."{TABLA_DEST}" ADD COLUMN IF NOT EXISTS grupo TEXT'))
        conn.execute(text(f'ALTER TABLE "{SCHEMA_DEST}"."{TABLA_DEST}" ADD COLUMN IF NOT EXISTS subgrupo TEXT'))
        conn.execute(text(f'ALTER TABLE "{SCHEMA_DEST}"."{TABLA_DEST}" ADD COLUMN IF NOT EXISTS status_gestion VARCHAR(50) DEFAULT \'Pendiente\''))
        conn.commit()
    print("✅ Estructura lista.")
except Exception as e:
    print(f"⚠️ Error estructura: {e}")
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

print("🚀 INICIANDO ETL OPEX (CON EXCEPCIONES CONIX AGREGADAS)...")

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
# 3. LISTAS DE EXCEPCIONES Y REGLAS
# ==============================================================================

# CONIX (NUEVO: Excepciones solicitadas)
excepciones_conix = """(
    '531520007', '531520005', '531520013', '531595003', '523040', '531520014', 
    '530525002', '531520012', '531520004', '531520001', '523030', '523010', 
    '530520007', '523071', '530525001', '531520009', '526020007', '531515001', 
    '530515002', '539520', '524570002', '531595004', '524570003', '530520002', 
    '530515001', '530595002', '531515006', '531016', '526515004', '531520003', 
    '531015', '524570005', '526020005', '523090', '526520001', '524570001', 
    '550505', '540505002', '526020003', '530595001', '526020004'
)"""

# GFO
excepciones_gfo = "('52991005', '53050503', '53051505', '53052005', '53052015')"

# NC SA
excepciones_nc_sa = """(
    '32022008', '31019001', '32022007', '31011024', '42021005', '31011015', '31011023', '31013005', '31021002', 
    '42021023', '42012021', '31021001', '32031019', '42021014', '32031020', '42011002', '42021001', '31011002', 
    '42021020', '42021002', '31011029', '31011030', '42021022', '42021024', '42021004', '42111201', '42021016'
)"""

# NC SPA
excepciones_nc_spa = """(
    '32011021', '32031308', '32011013', '32032901', '32031708', '32031314', '32011023', '32031507', '32031504',
    '32031503', '32011005', '31031005', '32011025', '32022005', '32011009', '32022003', '32031901', '32011024',
    '32011010', '32031903', '32031707', '32011007', '32022002', '32011003', '32011012', '32031801', '32031001',
    '32011002', '32011006', '32031403', '32011001', '31019001', '42021005'
)"""

# IN SA
excepciones_in_sa = """(
    '32114400', '32115200', '32113900', '31115800', '31110700', '31115900', '31115200', '31117400', '31116600',
    '31110100', '31115400', '31117000', '31117200', '31111000', '31115100', '31118200', '31118600', '31118700',
    '31115500', '31119100', '31118300', '31119500', '31118500', '31120000', '31121300', '32112600', '31116100',
    '31119600', '32114200', '31120500', '31121700', '31116400', '32111500', '31116500', '32112500', '32112701',
    '31116700', '32113400', '31116800', '31118400', '31119400', '32110200', '32110400', '32110900', '32112300',
    '31120700', '31121400', '42111201', '32111200', '32113600', '31117500', '31117800', '31120600', '31120900',
    '32114401', '32114500', '32114600', '42110400', '32115400', '32120100', '42110900', '42111000', '42110700',
    '31121900', '32110100', '31116200', '31116300', '31117600', '42111100', '42110300', '42111200', '42111400',
    '31116900', '31119300'
)"""

# LTC
excepciones_ltc = """(
    '31010401', '42801007', '32100805', '32100803', '32030101', '32100606', '32100404', '32101001', '32030204',
    '32100502', '32030105', '32101101', '32100101', '32100402', '32100607', '32101201', '32010112', '32010107',
    '32101103', '32010106', '32100612', '32100702', '32010110', '32100608', '32101004', '32100405', '32101104',
    '32100406', '32100102', '32010118', '32100501', '32100605', '32100603', '42801014', '32110005', '32030203',
    '32030104', '32100409', '32010101', '32110002', '32110010', '32010109', '32010103', '32010120', '32110003',
    '32100604', '32100408', '32100901', '32030202', '32100103', '32100403', '32100701', '32010119', '31010402',
    '31010305', '32100611', '31010701', '32010201', '32100801', '31010111', '32010117', '31010116', '32010116',
    '32100411', '32100413'
)"""

# NC LEASING CHILE
excepciones_nc_leasing = """(
    '31019001', '32011012', '32011003', '32011001', '32011002', '32031402', '32011006', '32031314', '32011013',
    '31021002', '32011010', '32031001', '31021001', '32031319', '32031504', '32022005', '32011007', '32031401',
    '32022002', '32031903', '32031801', '32031901', '32022003', '32011021', '42021004', '31019002', '42021030',
    '42011001', '32032101'
)"""

# AFI
excepciones_afi = "('42801007', '31010108')"

# FILTRO GENERAL PARA SQL SERVER
FILTER_SQL_SRV_GENERAL = """
AND DC.Com_Periodo >= '202501'
AND (DC.Cta_Codigo LIKE '31%' OR DC.Cta_Codigo LIKE '32%' OR DC.Cta_Codigo LIKE '42%')
"""

# FILTRO GENERAL PARA POSTGRESQL
def get_pg_filter_general(col_fecha, col_cuenta):
    return f"""
    AND {col_fecha}::date >= '2025-01-01' 
    AND ({col_cuenta}::text LIKE '31%%' OR {col_cuenta}::text LIKE '32%%' OR {col_cuenta}::text LIKE '42%%')
    """

# ==============================================================================
# 4. QUERIES DE EXTRACCIÓN
# ==============================================================================

# --- A. PostgreSQL (Histórico) ---
q_pg = {
    # --- CONIX: CORREGIDO CON EXCEPCIONES ---
    'CONIX': f"""
        SELECT 'CONIX' as empresa, 
               fecha_corte, 
               d_fecha_documento::text as fecha_transaccion, 
               k_sc_codigo_cuenta as cuenta_contable, 
               n_nit as id_proveedor, 
               sc_nombre as nombre_tercero, 
               CONCAT_WS(' ', sc_nombre_cuenta, sv_observaciones, sc_nombre_centro_costo) as descripcion_gasto, 
               n_valor as valor 
        FROM control_gestion.libros_diarios_conix 
        WHERE 1=1 
          AND d_fecha_documento::date >= '2025-01-01'
          AND k_sc_codigo_cuenta::text LIKE '5%%'
          AND k_sc_codigo_cuenta::text NOT IN {excepciones_conix}
    """,
    
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
                       WHEN d_c = 'D' THEN valor_l1 
                       WHEN d_c = 'C' THEN -valor_l1 
                       ELSE 0 
                   END 
               AS NUMERIC) as valor 
        FROM control_gestion.libros_diarios_gfo 
        WHERE 1=1 
          AND fecha_docto::date >= '2024-01-01'
          AND cuenta::text LIKE '5%%'
          AND cuenta::text NOT IN {excepciones_gfo}
    """,
    
    'LTCP': f"""SELECT 'LTCP' as empresa, fecha_corte, "FEC DOC"::text as fecha_transaccion, "CUENTA" as cuenta_contable, "ANEXO" as id_proveedor, NULL as nombre_tercero, CONCAT_WS(' ', "CONCEPTO", "C COSTO") as descripcion_gasto, (COALESCE("DEBE  - MN", 0) - COALESCE("HABER - MN", 0)) as valor FROM control_gestion.libros_diarios_ltcp WHERE 1=1 {get_pg_filter_general('"FEC DOC"', '"CUENTA"')}""",
    'LTCP2': f"""SELECT 'LTCP2' as empresa, fecha_corte, "FEC DOC"::text as fecha_transaccion, "CUENTA" as cuenta_contable, "ANEXO" as id_proveedor, NULL as nombre_tercero, CONCAT_WS(' ', "CONCEPTO", "C COSTO") as descripcion_gasto, (COALESCE("DEBE  - MN", 0) - COALESCE("HABER - MN", 0)) as valor FROM control_gestion.libros_diarios_ltcp2 WHERE 1=1 {get_pg_filter_general('"FEC DOC"', '"CUENTA"')}""",
    'NCPF': f"""SELECT 'NCPF' as empresa, fecha_corte, "FEC DOC"::text as fecha_transaccion, "CUENTA" as cuenta_contable, "ANEXO" as id_proveedor, NULL as nombre_tercero, CONCAT_WS(' ', "CONCEPTO", "C COSTO") as descripcion_gasto, (COALESCE("DEBE  - MN", 0) - COALESCE("HABER - MN", 0)) as valor FROM control_gestion.libros_diarios_ncpf WHERE 1=1 {get_pg_filter_general('"FEC DOC"', '"CUENTA"')}""",
    'NC LEASING PERU': f"""SELECT 'NC LEASING PERU' as empresa, fecha_corte, "fec_doc"::text as fecha_transaccion, "cuenta" as cuenta_contable, "anexo" as id_proveedor, NULL as nombre_tercero, CONCAT_WS(' ', "concepto", "centro_costo") as descripcion_gasto, (COALESCE("debe_mn", 0) - COALESCE("haber_mn", 0)) as valor FROM control_gestion.libros_diarios_nc_leasing WHERE 1=1 {get_pg_filter_general('"fec_doc"', 'cuenta')}"""
}

# --- B. SQL Server (Histórico desde 2024) ---
f_afi = "CAST(LEFT(DC.Com_Periodo, 4) + '-' + SUBSTRING(DC.Com_Periodo, 5, 2) + '-01' AS DATE)"
sql_afi = f"""SELECT 'AFI' as empresa, CONVERT(VARCHAR(10), {f_afi}, 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM dbo.Detalle_Comprobante DC LEFT JOIN dbo.Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN dbo.Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN dbo.Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo WHERE DC.Com_Numero IS NOT NULL {FILTER_SQL_SRV_GENERAL} AND DC.Cta_Codigo NOT IN {excepciones_afi}"""

sql_ltc = f"""SELECT 'LTC' as empresa, CONVERT(VARCHAR(10), CAST(LEFT(DC.Com_Periodo, 4) + '-' + SUBSTRING(DC.Com_Periodo, 5, 2) + '-01' AS DATE), 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM dbo.Detalle_Comprobante DC LEFT JOIN dbo.Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN dbo.Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN dbo.Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo WHERE DC.Com_Numero IS NOT NULL {FILTER_SQL_SRV_GENERAL} AND DC.Cta_Codigo NOT IN {excepciones_ltc}"""

f_nc = "CAST(SUBSTRING(DC.Com_Periodo, 1, 4) + '-' + SUBSTRING(DC.Com_Periodo, 5, 2) + '-01' AS DATE)"
sql_nc_spa = f"""SELECT 'NC SPA' as empresa, CONVERT(VARCHAR(10), {f_nc}, 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM Detalle_Comprobante DC LEFT JOIN Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo LEFT JOIN Comprobante C ON DC.Com_Numero = C.Com_Numero AND DC.Com_Periodo = C.Com_Periodo WHERE C.Com_Estado <> 'A' {FILTER_SQL_SRV_GENERAL} AND DC.Cta_Codigo NOT IN {excepciones_nc_spa}"""

sql_nc_l = f"""SELECT 'NC LEASING CHILE' as empresa, CONVERT(VARCHAR(10), {f_nc}, 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM Detalle_Comprobante DC LEFT JOIN Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo LEFT JOIN Comprobante C ON DC.Com_Numero = C.Com_Numero AND DC.Com_Periodo = C.Com_Periodo WHERE C.Com_Estado <> 'A' {FILTER_SQL_SRV_GENERAL} AND DC.Cta_Codigo NOT IN {excepciones_nc_leasing}"""

sql_nc_sa = f"""SELECT 'NC SA' as empresa, CONVERT(VARCHAR(10), {f_nc}, 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM Detalle_Comprobante DC LEFT JOIN Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo LEFT JOIN Comprobante C ON DC.Com_Numero = C.Com_Numero AND DC.Com_Periodo = C.Com_Periodo WHERE C.Com_Estado <> 'A' AND CAST(SUBSTRING(DC.Com_Periodo, 1, 4) AS INT) >= 2025 AND (DC.Cta_Codigo LIKE '3%' OR DC.Cta_Codigo LIKE '42%') AND DC.Cta_Codigo NOT IN {excepciones_nc_sa}"""

f_insa = "CAST(SUBSTRING(DC.Com_Periodo, 1, 4) + '-' + SUBSTRING(DC.Com_Periodo, 5, 2) + '-01' AS DATE)"
sql_in_sa = f"""SELECT 'IN SA' as empresa, CONVERT(VARCHAR(10), {f_insa}, 23) as fecha_transaccion, DC.Cta_Codigo as cuenta_contable, DC.Cli_Rut as id_proveedor, CLI.Cli_Nombre as nombre_tercero, ISNULL(DC.Dco_Glosa,'') + ' ' + ISNULL(CDC.Cdc_glosa,'') + ' ' + ISNULL(CTA.Cta_Glosa,'') as descripcion_gasto, (CASE WHEN DC.Dco_TipoDH = 'D' THEN DC.Dco_Valor ELSE 0 END - CASE WHEN DC.Dco_TipoDH = 'H' THEN DC.Dco_Valor ELSE 0 END) as valor FROM Detalle_Comprobante DC LEFT JOIN Cliente CLI ON DC.Cli_Rut = CLI.Cli_Rut LEFT JOIN Cuenta CTA ON DC.Cta_Codigo = CTA.Cta_Codigo LEFT JOIN Centro_de_Costo CDC ON DC.Cdc_Codigo = CDC.Cdc_Codigo LEFT JOIN Comprobante C ON DC.Com_Numero = C.Com_Numero AND DC.Com_Periodo = C.Com_Periodo WHERE C.Com_Estado <> 'A' {FILTER_SQL_SRV_GENERAL} AND DC.Cta_Codigo NOT IN {excepciones_in_sa}"""

# INCOFIN LEASING (OPTIMIZADA)
sql_in_l = """
SELECT 'INCOFIN LEASING' as empresa, 
       CONVERT(VARCHAR(10), CAST(c.fecha_comp AS DATE), 23) as fecha_transaccion, 
       cd.cod_cuenta as cuenta_contable, 
       ISNULL(CAST(cd.con_analisis1 AS VARCHAR), '') + '-' + ISNULL(CAST(cd.dv_con_analisis1 AS VARCHAR), '') as id_proveedor,
       NULL as nombre_tercero, 
       ISNULL(cd.glosa_det_comp,'') as descripcion_gasto, 
       (cd.mto_deb_$ - cd.mto_hab_$) as valor 
FROM dbo.t_comprobante_detalle cd 
INNER JOIN dbo.t_comprobante c ON cd.num_comp = c.num_comp 
WHERE c.fecha_comp >= '2025-01-01'
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
                for df in pd.read_sql(q, c, chunksize=10000):
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
# 6. ESTRUCTURA FINAL (IA)
# ==============================================================================
print("🔨 Ajustando estructura para IA...")
try:
    with engine_pg.connect() as conn:
        conn.execute(text(f'ALTER TABLE "{SCHEMA_DEST}"."{TABLA_DEST}" ADD COLUMN IF NOT EXISTS id_transaccion SERIAL PRIMARY KEY'))
        conn.execute(text(f'ALTER TABLE "{SCHEMA_DEST}"."{TABLA_DEST}" ADD COLUMN IF NOT EXISTS grupo TEXT'))
        conn.execute(text(f'ALTER TABLE "{SCHEMA_DEST}"."{TABLA_DEST}" ADD COLUMN IF NOT EXISTS subgrupo TEXT'))
        conn.execute(text(f'ALTER TABLE "{SCHEMA_DEST}"."{TABLA_DEST}" ADD COLUMN IF NOT EXISTS status_gestion VARCHAR(50) DEFAULT \'Pendiente\''))
        conn.execute(text(f'ALTER TABLE "{SCHEMA_DEST}"."{TABLA_DEST}" ADD COLUMN IF NOT EXISTS clasificacion_manual BOOLEAN DEFAULT FALSE'))
        conn.commit()
    print("✅ Estructura lista.")
except Exception as e:
    print(f"⚠️ Error estructura: {e}")
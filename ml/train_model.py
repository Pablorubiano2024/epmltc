import pandas as pd
import numpy as np
import os
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# ==============================================================================
# 1. CONFIGURACIÓN DE RUTAS Y ARCHIVOS
# ==============================================================================
# Obtenemos la ruta base del proyecto (subimos un nivel desde la carpeta 'ml')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Rutas de Archivos
FILE_NAME = "Opex Real 2025 (1).xlsx" # <--- ASEGÚRATE QUE ESTE NOMBRE SEA EXACTO
DATA_PATH = os.path.join(BASE_DIR, "data", FILE_NAME)
MODELS_DIR = os.path.join(BASE_DIR, "backend", "ml_models")

# Aseguramos que la carpeta de destino exista
os.makedirs(MODELS_DIR, exist_ok=True)

# ==============================================================================
# 2. CONFIGURACIÓN DE COLUMNAS (EXCEL HISTÓRICO)
# ==============================================================================
COL_GRUPO    = "Grupo"
COL_SUBGRUPO = "Subgrupo"
COL_DESC     = "Glosa Documento nuevo"
COL_CUENTA   = "Código Cuenta"
COL_PROV     = "Rut Nuevo" # Usamos RUT para ser consistentes con el ETL

print(f"🚀 INICIANDO ENTRENAMIENTO...")
print(f"   📂 Leyendo datos desde: {DATA_PATH}")

# ==============================================================================
# 3. CARGA Y LIMPIEZA DE DATOS
# ==============================================================================
if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(f"❌ No se encontró el archivo en {DATA_PATH}. Verifica la carpeta 'data'.")

try:
    df = pd.read_excel(DATA_PATH)
except Exception as e:
    print(f"   ⚠️ Error leyendo Excel: {e}")
    exit()

print(f"   📊 Total registros iniciales: {len(df)}")

# Eliminar filas sin clasificación (Grupo es obligatorio para aprender)
df = df.dropna(subset=[COL_GRUPO])

# Rellenar nulos en textos
df[COL_DESC] = df[COL_DESC].fillna('')
df[COL_PROV] = df[COL_PROV].astype(str).fillna('')
df[COL_SUBGRUPO] = df[COL_SUBGRUPO].fillna('General')

# --- INGENIERÍA DE CARACTERÍSTICAS ---
# Creamos la "Huella Digital" uniendo: Cuenta + RUT + Descripción
print("   🧠 Generando vectores de texto...")
df['TEXTO_COMBINADO'] = (
    df[COL_CUENTA].astype(str) + " " +
    df[COL_PROV].astype(str) + " " +
    df[COL_DESC].astype(str)
).str.lower()

X = df['TEXTO_COMBINADO']

# ==============================================================================
# 4. ENTRENAMIENTO MODELO A: GRUPO
# ==============================================================================
print("\n🤖 Entrenando Modelo 1: GRUPO...")
y_grupo = df[COL_GRUPO]

# Split 80/20
X_train, X_test, y_train, y_test = train_test_split(X, y_grupo, test_size=0.2, random_state=42)

pipeline_grupo = Pipeline([
    ('tfidf', TfidfVectorizer(max_features=5000, stop_words='english', ngram_range=(1,2))),
    ('clf', RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=42))
])

pipeline_grupo.fit(X_train, y_train)
acc_grupo = accuracy_score(y_test, pipeline_grupo.predict(X_test))
print(f"   ✅ Precisión (Accuracy): {acc_grupo:.2%}")

# ==============================================================================
# 5. ENTRENAMIENTO MODELO B: SUBGRUPO
# ==============================================================================
print("\n🤖 Entrenando Modelo 2: SUBGRUPO...")
y_subgrupo = df[COL_SUBGRUPO]

X_train_s, X_test_s, y_train_s, y_test_s = train_test_split(X, y_subgrupo, test_size=0.2, random_state=42)

pipeline_subgrupo = Pipeline([
    ('tfidf', TfidfVectorizer(max_features=5000, stop_words='english', ngram_range=(1,2))),
    ('clf', RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=42))
])

pipeline_subgrupo.fit(X_train_s, y_train_s)
acc_subgrupo = accuracy_score(y_test_s, pipeline_subgrupo.predict(X_test_s))
print(f"   ✅ Precisión (Accuracy): {acc_subgrupo:.2%}")

# ==============================================================================
# 6. GUARDAR MODELOS (.PKL)
# ==============================================================================
print("\n💾 Guardando cerebros en backend/ml_models/ ...")

path_grupo = os.path.join(MODELS_DIR, 'modelo_grupo.pkl')
path_subgrupo = os.path.join(MODELS_DIR, 'modelo_subgrupo.pkl')

joblib.dump(pipeline_grupo, path_grupo)
joblib.dump(pipeline_subgrupo, path_subgrupo)

print(f"   ✅ Modelo Grupo guardado en: {path_grupo}")
print(f"   ✅ Modelo Subgrupo guardado en: {path_subgrupo}")
print("\n🎉 ENTRENAMIENTO FINALIZADO EXITOSAMENTE.")
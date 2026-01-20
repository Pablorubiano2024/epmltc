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
# 1. CONFIGURACIÓN
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE_NAME = "Opex Real 2025 (1).xlsx" # Asegúrate que este sea el nombre correcto en tu carpeta data
DATA_PATH = os.path.join(BASE_DIR, "data", FILE_NAME)
MODELS_DIR = os.path.join(BASE_DIR, "backend", "ml_models")

os.makedirs(MODELS_DIR, exist_ok=True)

# Columnas del Excel
COL_GRUPO    = "Grupo"
COL_SUBGRUPO = "Subgrupo"
COL_DESC     = "Glosa Documento nuevo"
COL_CUENTA   = "Código Cuenta"
COL_PROV     = "Rut Nuevo" # Usamos RUT para mayor precisión

print(f"🚀 INICIANDO ENTRENAMIENTO MEJORADO...")

# ==============================================================================
# 2. CARGA DE DATOS
# ==============================================================================
if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(f"❌ Falta el archivo: {DATA_PATH}")

try:
    df = pd.read_excel(DATA_PATH)
except:
    df = pd.read_excel(DATA_PATH, engine='openpyxl')

# Limpieza
df = df.dropna(subset=[COL_GRUPO])
df[COL_DESC] = df[COL_DESC].fillna('')
df[COL_PROV] = df[COL_PROV].astype(str).fillna('')
df[COL_SUBGRUPO] = df[COL_SUBGRUPO].fillna('General')

# --- INGENIERÍA DE CARACTERÍSTICAS (MEJORADA) ---
# Usamos: Cuenta + RUT + Descripción
# Nota: No agregamos 'Empresa' aquí porque queremos que el modelo aprenda
# reglas universales (ej: "Uber" es transporte en Chile y en Perú).
df['TEXTO_COMBINADO'] = (
    df[COL_CUENTA].astype(str) + " " +
    df[COL_PROV].astype(str) + " " +
    df[COL_DESC].astype(str)
).str.lower()

X = df['TEXTO_COMBINADO']

print(f"📊 Registros para entrenar: {len(df)}")

# ==============================================================================
# 3. ENTRENAMIENTO (PARAMETROS OPTIMIZADOS)
# ==============================================================================

# Aumentamos n_estimators a 150 y max_features a 6000 para mayor precisión

# --- MODELO GRUPO ---
print("\n🤖 Entrenando GRUPO (Configuración Robusta)...")
y_grupo = df[COL_GRUPO]
X_train, X_test, y_train, y_test = train_test_split(X, y_grupo, test_size=0.2, random_state=42)

pipeline_grupo = Pipeline([
    ('tfidf', TfidfVectorizer(max_features=6000, stop_words='english', ngram_range=(1,2))),
    ('clf', RandomForestClassifier(n_estimators=150, n_jobs=-1, random_state=42))
])
pipeline_grupo.fit(X_train, y_train)
print(f"   ✅ Precisión GRUPO: {pipeline_grupo.score(X_test, y_test):.2%}")

# --- MODELO SUBGRUPO ---
print("\n🤖 Entrenando SUBGRUPO (Configuración Robusta)...")
y_subgrupo = df[COL_SUBGRUPO]
X_train_s, X_test_s, y_train_s, y_test_s = train_test_split(X, y_subgrupo, test_size=0.2, random_state=42)

pipeline_subgrupo = Pipeline([
    ('tfidf', TfidfVectorizer(max_features=6000, stop_words='english', ngram_range=(1,2))),
    ('clf', RandomForestClassifier(n_estimators=150, n_jobs=-1, random_state=42))
])
pipeline_subgrupo.fit(X_train_s, y_train_s)
print(f"   ✅ Precisión SUBGRUPO: {pipeline_subgrupo.score(X_test_s, y_test_s):.2%}")

# ==============================================================================
# 4. GUARDADO
# ==============================================================================
print("\n💾 Guardando modelos...")
joblib.dump(pipeline_grupo, os.path.join(MODELS_DIR, 'modelo_grupo.pkl'))
joblib.dump(pipeline_subgrupo, os.path.join(MODELS_DIR, 'modelo_subgrupo.pkl'))
print("🎉 FINALIZADO.")
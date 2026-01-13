from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import joblib
import os
import sys

# Importación absoluta desde el paquete backend
from backend.database import get_db

router = APIRouter()

# ==============================================================================
# 1. CARGA DE MODELOS DE INTELIGENCIA ARTIFICIAL
# ==============================================================================
# Calculamos la ruta absoluta a la carpeta backend/ml_models
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) # carpeta routers/
BACKEND_DIR = os.path.dirname(CURRENT_DIR)               # carpeta backend/
MODEL_DIR = os.path.join(BACKEND_DIR, "ml_models")

print(f"🧠 Buscando modelos en: {MODEL_DIR} ...")

try:
    path_grupo = os.path.join(MODEL_DIR, "modelo_grupo.pkl")
    path_subgrupo = os.path.join(MODEL_DIR, "modelo_subgrupo.pkl")
    
    if os.path.exists(path_grupo) and os.path.exists(path_subgrupo):
        model_grupo = joblib.load(path_grupo)
        model_subgrupo = joblib.load(path_subgrupo)
        print("✅ Modelos de IA cargados correctamente.")
    else:
        print("⚠️ No se encontraron los archivos .pkl. La predicción no funcionará.")
        model_grupo = None
        model_subgrupo = None
except Exception as e:
    print(f"❌ Error cargando modelos: {e}")
    model_grupo = None
    model_subgrupo = None

# ==============================================================================
# 2. ESQUEMAS DE DATOS (Pydantic)
# ==============================================================================
class GastoInput(BaseModel):
    empresa: str
    cuenta_contable: str
    descripcion_gasto: str
    id_proveedor: Optional[str] = ""
    nombre_tercero: Optional[str] = ""

# ==============================================================================
# 3. ENDPOINTS (RUTAS)
# ==============================================================================

# --- A. DASHBOARD (RESUMEN MENSUAL) ---
@router.get("/summary")
def get_opex_summary(year: int = 2025, db: Session = Depends(get_db)):
    """
    Obtiene el total de gastos agrupado por Empresa y Mes.
    Realiza un CAST de fecha_transaccion a DATE para evitar errores de tipo.
    """
    try:
        sql = text("""
            SELECT 
                empresa,
                TO_CHAR(CAST(fecha_transaccion AS DATE), 'YYYY-MM') as periodo,
                SUM(valor) as total
            FROM control_gestion.libros_diarios_consolidados
            WHERE EXTRACT(YEAR FROM CAST(fecha_transaccion AS DATE)) = :year
              AND (cuenta_contable LIKE '31%' OR cuenta_contable LIKE '32%' OR cuenta_contable LIKE '42%')
            GROUP BY empresa, TO_CHAR(CAST(fecha_transaccion AS DATE), 'YYYY-MM')
            ORDER BY periodo, empresa
        """)
        
        result = db.execute(sql, {"year": year}).fetchall()
        
        return [
            {"empresa": row[0], "periodo": row[1], "total": float(row[2])}
            for row in result
        ]
    except Exception as e:
        print(f"❌ Error en SQL Summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error consultando base de datos: {str(e)}")

# --- B. EXPLORADOR DE DATOS (FILTROS) ---
@router.get("/transactions")
def get_transactions(
    start_date: str, 
    end_date: str, 
    empresas: str, # Recibe string separado por comas: "AFI,CONIX"
    cuenta: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        empresa_list = empresas.split(",")
        
        # Base de la consulta
        sql_query = """
            SELECT * FROM control_gestion.libros_diarios_consolidados
            WHERE CAST(fecha_transaccion AS DATE) BETWEEN :start AND :end
            AND empresa = ANY(:emp_list)
        """
        params = {"start": start_date, "end": end_date, "emp_list": empresa_list}
        
        # Filtro opcional por cuenta
        if cuenta:
            sql_query += " AND cuenta_contable LIKE :cta"
            params["cta"] = f"{cuenta}%"
            
        # Límite de seguridad para no explotar la RAM
        sql_query += " LIMIT 5000"
            
        result = db.execute(text(sql_query), params).fetchall()
        
        # Convertir a lista de diccionarios
        return [dict(row._mapping) for row in result]
        
    except Exception as e:
        print(f"❌ Error en Transacciones: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- C. PENDIENTES DE CLASIFICACIÓN (SIMULACIÓN) ---
@router.get("/pending-classification")
def get_pending_classification(db: Session = Depends(get_db)):
    """
    Trae una muestra de gastos OPEX para probar la IA.
    En el futuro, esto debería filtrar 'WHERE grupo IS NULL'.
    """
    try:
        sql = text("""
            SELECT * FROM control_gestion.libros_diarios_consolidados
            WHERE (cuenta_contable LIKE '31%' OR cuenta_contable LIKE '32%' OR cuenta_contable LIKE '42%')
            ORDER BY RANDOM() 
            LIMIT 20
        """)
        result = db.execute(sql).fetchall()
        return [dict(row._mapping) for row in result]
    except Exception as e:
        print(f"❌ Error obteniendo pendientes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- D. PREDICCIÓN (MACHINE LEARNING) ---
@router.post("/predict")
def predict_gastos(gastos: List[GastoInput]):
    """
    Recibe una lista de gastos, aplica los modelos Random Forest y devuelve clasificación.
    """
    if not model_grupo or not model_subgrupo:
        raise HTTPException(status_code=500, detail="Los modelos de IA no están cargados en el servidor.")

    try:
        # Convertir input a DataFrame
        data = [g.dict() for g in gastos]
        df = pd.DataFrame(data)
        
        # Preprocesamiento idéntico al entrenamiento
        # Cuenta + ID Proveedor + Descripción
        df['TEXTO_COMBINADO'] = (
            df['cuenta_contable'].astype(str) + " " +
            df['id_proveedor'].fillna('').astype(str) + " " +
            df['descripcion_gasto'].fillna('').astype(str)
        ).str.lower()
        
        # Predicción Grupo
        grupos = model_grupo.predict(df['TEXTO_COMBINADO'])
        probs_g = model_grupo.predict_proba(df['TEXTO_COMBINADO'])
        
        # Predicción Subgrupo
        subgrupos = model_subgrupo.predict(df['TEXTO_COMBINADO'])
        
        # Armar respuesta
        response = []
        for i, row in df.iterrows():
            confianza = max(probs_g[i]) * 100
            response.append({
                **data[i],
                "grupo_predicho": grupos[i],
                "subgrupo_predicho": subgrupos[i],
                "confianza_grupo": round(confianza, 1)
            })
            
        return response

    except Exception as e:
        print(f"❌ Error en predicción: {e}")
        raise HTTPException(status_code=500, detail=f"Error en motor de IA: {str(e)}")
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import joblib
import os
import sys

# Importación absoluta
from backend.database import get_db

router = APIRouter()

# ==============================================================================
# 1. CARGA DE MODELOS
# ==============================================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
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
        print("⚠️ No se encontraron los archivos .pkl.")
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
    id_transaccion: Optional[int] = None # Necesario para guardar después
    empresa: str
    cuenta_contable: str
    descripcion_gasto: str
    id_proveedor: Optional[str] = ""
    nombre_tercero: Optional[str] = ""

class UpdateClasificacion(BaseModel):
    id_transaccion: int
    grupo: str
    subgrupo: str

# ==============================================================================
# 3. ENDPOINTS
# ==============================================================================

# --- A. DASHBOARD ---
@router.get("/summary")
def get_opex_summary(year: int = 2025, db: Session = Depends(get_db)):
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
        return [{"empresa": r[0], "periodo": r[1], "total": float(r[2])} for r in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- B. EXPLORADOR ---
@router.get("/transactions")
def get_transactions(start_date: str, end_date: str, empresas: str, cuenta: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        empresa_list = empresas.split(",")
        sql_query = """
            SELECT * FROM control_gestion.libros_diarios_consolidados
            WHERE CAST(fecha_transaccion AS DATE) BETWEEN :start AND :end
            AND empresa = ANY(:emp_list)
        """
        params = {"start": start_date, "end": end_date, "emp_list": empresa_list}
        
        if cuenta:
            sql_query += " AND cuenta_contable LIKE :cta"
            params["cta"] = f"{cuenta}%"
            
        sql_query += " LIMIT 5000"
        result = db.execute(text(sql_query), params).fetchall()
        return [dict(row._mapping) for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- C. PENDIENTES (MODIFICADO PARA TRAER ID Y FILTRAR NULOS) ---
@router.get("/pending-classification")
def get_pending_classification(limit: int = 50, db: Session = Depends(get_db)):
    try:
        # Filtramos donde 'grupo' es NULL o vacío
        sql = text("""
            SELECT * FROM control_gestion.libros_diarios_consolidados
            WHERE (grupo IS NULL OR grupo = '')
            AND (cuenta_contable LIKE '31%' OR cuenta_contable LIKE '32%' OR cuenta_contable LIKE '42%')
            ORDER BY fecha_transaccion DESC
            LIMIT :limit
        """)
        result = db.execute(sql, {"limit": limit}).fetchall()
        return [dict(row._mapping) for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- D. PREDICCIÓN ---
@router.post("/predict")
def predict_gastos(gastos: List[GastoInput]):
    if not model_grupo or not model_subgrupo:
        raise HTTPException(status_code=500, detail="Modelos no cargados.")

    try:
        data = [g.dict() for g in gastos]
        df = pd.DataFrame(data)
        
        # Feature Engineering
        df['TEXTO_COMBINADO'] = (
            df['cuenta_contable'].astype(str) + " " +
            df['id_proveedor'].fillna('').astype(str) + " " +
            df['descripcion_gasto'].fillna('').astype(str)
        ).str.lower()
        
        # Predicciones
        grupos = model_grupo.predict(df['TEXTO_COMBINADO'])
        probs_g = model_grupo.predict_proba(df['TEXTO_COMBINADO'])
        subgrupos = model_subgrupo.predict(df['TEXTO_COMBINADO'])
        
        response = []
        for i, row in df.iterrows():
            confianza = max(probs_g[i]) * 100
            response.append({
                **data[i],
                "grupo_predicho": grupos[i],
                "subgrupo_predicho": subgrupos[i],
                "confianza": round(confianza, 1)
            })
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- E. GUARDAR CAMBIOS (NUEVO) ---
@router.put("/update-batch")
def update_batch_classification(updates: List[UpdateClasificacion], db: Session = Depends(get_db)):
    try:
        count = 0
        for item in updates:
            sql = text("""
                UPDATE control_gestion.libros_diarios_consolidados
                SET grupo = :g, subgrupo = :s
                WHERE id_transaccion = :id
            """)
            db.execute(sql, {"g": item.grupo, "s": item.subgrupo, "id": item.id_transaccion})
            count += 1
            
        db.commit()
        return {"status": "success", "updated_rows": count}
    except Exception as e:
        db.rollback()
        print(f"❌ Error DB Update: {e}")
        raise HTTPException(status_code=500, detail=str(e))
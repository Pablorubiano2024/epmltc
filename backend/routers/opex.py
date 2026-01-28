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

# --- CARGA MODELOS ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
MODEL_DIR = os.path.join(BACKEND_DIR, "ml_models")

try:
    model_grupo = joblib.load(os.path.join(MODEL_DIR, "modelo_grupo.pkl"))
    model_subgrupo = joblib.load(os.path.join(MODEL_DIR, "modelo_subgrupo.pkl"))
except:
    model_grupo, model_subgrupo = None, None

# --- ESQUEMAS ---
class GastoInput(BaseModel):
    id_transaccion: Optional[int] = None
    empresa: str
    cuenta_contable: str
    descripcion_gasto: str
    id_proveedor: Optional[str] = ""
    nombre_tercero: Optional[str] = ""

class UpdateGestion(BaseModel):
    id_transaccion: int
    grupo: Optional[str] = None
    subgrupo: Optional[str] = None
    status_gestion: Optional[str] = None

class UpdateProveedor(BaseModel):
    nombre_tercero: str
    status_gestion: Optional[str] = None
    grupo: Optional[str] = None
    subgrupo: Optional[str] = None

# --- ENDPOINTS ---

# 1. LISTAS PARA DESPLEGABLES (NUEVO)
@router.get("/categories")
def get_unique_categories(db: Session = Depends(get_db)):
    """Devuelve listas únicas de Grupos y Subgrupos para los selectbox del frontend"""
    try:
        # Obtenemos grupos únicos
        res_g = db.execute(text("SELECT DISTINCT grupo FROM control_gestion.libros_diarios_consolidados WHERE grupo IS NOT NULL ORDER BY grupo")).fetchall()
        grupos = [r[0] for r in res_g if r[0]]

        # Obtenemos subgrupos únicos
        res_s = db.execute(text("SELECT DISTINCT subgrupo FROM control_gestion.libros_diarios_consolidados WHERE subgrupo IS NOT NULL ORDER BY subgrupo")).fetchall()
        subgrupos = [r[0] for r in res_s if r[0]]

        return {"grupos": grupos, "subgrupos": subgrupos}
    except Exception as e:
        print(f"❌ Error categories: {e}")
        return {"grupos": [], "subgrupos": []}

# 2. DASHBOARD
@router.get("/summary")
def get_opex_summary(year: int = 2025, db: Session = Depends(get_db)):
    try:
        sql = text("""
            SELECT empresa, TO_CHAR(CAST(fecha_corte AS DATE), 'YYYY-MM'), SUM(valor)
            FROM control_gestion.libros_diarios_consolidados
            WHERE EXTRACT(YEAR FROM CAST(fecha_corte AS DATE)) = :year
              AND (cuenta_contable LIKE '31%' OR cuenta_contable LIKE '32%' OR cuenta_contable LIKE '42%' OR cuenta_contable LIKE '5%')
            GROUP BY empresa, TO_CHAR(CAST(fecha_corte AS DATE), 'YYYY-MM')
            ORDER BY 2, 1
        """)
        result = db.execute(sql, {"year": year}).fetchall()
        return [{"empresa": r[0], "periodo": r[1], "total": float(r[2])} for r in result]
    except Exception as e:
        raise HTTPException(500, str(e))

# 3. TRANSACCIONES
@router.get("/transactions")
def get_transactions(start_date: str, end_date: str, empresas: str, cuenta: Optional[str]=None, proveedor: Optional[str]=None, limit: int=0, db: Session = Depends(get_db)):
    try:
        emp_list = empresas.split(",")
        sql = """
            SELECT id_transaccion, empresa, fecha_corte, fecha_transaccion, cuenta_contable, id_proveedor, nombre_tercero, descripcion_gasto, valor,
            COALESCE(grupo, 'Sin Clasificar') as grupo,
            COALESCE(subgrupo, 'General') as subgrupo,
            COALESCE(status_gestion, 'Pendiente') as status_gestion,
            COALESCE(clasificacion_manual, FALSE) as clasificacion_manual
            FROM control_gestion.libros_diarios_consolidados
            WHERE CAST(fecha_corte AS DATE) BETWEEN :start AND :end
            AND empresa = ANY(:emp_list)
        """
        params = {"start": start_date, "end": end_date, "emp_list": emp_list}
        
        if cuenta:
            sql += " AND cuenta_contable LIKE :cta"
            params["cta"] = f"{cuenta}%"
        else:
            if not proveedor:
                sql += " AND (cuenta_contable LIKE '31%' OR cuenta_contable LIKE '32%' OR cuenta_contable LIKE '42%' OR cuenta_contable LIKE '5%')"

        if proveedor:
            sql += " AND nombre_tercero ILIKE :prov"
            params["prov"] = f"%{proveedor}%"

        sql += " ORDER BY fecha_corte DESC, valor DESC"
        if limit > 0: sql += f" LIMIT {limit}"
            
        res = db.execute(text(sql), params).fetchall()
        return [dict(row._mapping) for row in res]
    except Exception as e:
        raise HTTPException(500, str(e))

# 4. PENDIENTES
@router.get("/pending-classification")
def get_pending(limit: int = 50, db: Session = Depends(get_db)):
    try:
        sql = text("""
            SELECT * FROM control_gestion.libros_diarios_consolidados
            WHERE (grupo IS NULL OR grupo = '')
            AND (clasificacion_manual IS FALSE OR clasificacion_manual IS NULL)
            AND (cuenta_contable LIKE '31%' OR cuenta_contable LIKE '32%' OR cuenta_contable LIKE '42%' OR cuenta_contable LIKE '5%')
            ORDER BY fecha_corte DESC LIMIT :limit
        """)
        res = db.execute(sql, {"limit": limit}).fetchall()
        return [dict(row._mapping) for row in res]
    except Exception as e:
        raise HTTPException(500, str(e))

# 5. PREDICT
@router.post("/predict")
def predict(gastos: List[GastoInput]):
    if not model_grupo: raise HTTPException(500, "Modelos no cargados")
    try:
        data = [g.dict() for g in gastos]
        df = pd.DataFrame(data)
        df['txt'] = (df['cuenta_contable'].astype(str)+" "+df['id_proveedor'].fillna('').astype(str)+" "+df['descripcion_gasto'].fillna('').astype(str)).str.lower()
        
        grupos = model_grupo.predict(df['txt'])
        probs = model_grupo.predict_proba(df['txt'])
        subs = model_subgrupo.predict(df['txt'])
        
        resp = []
        for i, row in df.iterrows():
            resp.append({**data[i], "grupo_predicho": grupos[i], "subgrupo_predicho": subs[i], "confianza": round(max(probs[i])*100, 1)})
        return resp
    except Exception as e: raise HTTPException(500, str(e))

# 6. UPDATE BATCH (ID)
@router.put("/update-batch")
def update_batch(updates: List[UpdateGestion], db: Session = Depends(get_db)):
    try:
        cnt = 0
        for i in updates:
            clauses = []
            p = {"id": i.id_transaccion}
            if i.grupo: clauses.append("grupo = :g"); p["g"] = i.grupo
            if i.subgrupo: clauses.append("subgrupo = :s"); p["s"] = i.subgrupo
            if i.status_gestion: clauses.append("status_gestion = :st"); p["st"] = i.status_gestion
            
            if clauses:
                db.execute(text(f"UPDATE control_gestion.libros_diarios_consolidados SET {', '.join(clauses)} WHERE id_transaccion = :id"), p)
                cnt += 1
        db.commit()
        return {"status": "success", "updated_rows": cnt}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))

# 7. UPDATE PROVEEDOR (MASIVO + FIX MANUAL)
@router.put("/update-provider-status")
def update_provider_status(updates: List[UpdateProveedor], db: Session = Depends(get_db)):
    try:
        cnt = 0
        print(f"🔄 Actualizando {len(updates)} proveedores...")
        for i in updates:
            clauses = []
            p = {"prov": i.nombre_tercero}
            
            if i.status_gestion:
                clauses.append("status_gestion = :st")
                p["st"] = i.status_gestion
            
            # Si se envía grupo/subgrupo, se marca como MANUAL
            if i.grupo or i.subgrupo:
                if i.grupo: clauses.append("grupo = :g"); p["g"] = i.grupo
                if i.subgrupo: clauses.append("subgrupo = :s"); p["s"] = i.subgrupo
                # LA CLAVE: Forzar la bandera manual
                clauses.append("clasificacion_manual = TRUE")

            if clauses:
                sql = text(f"""
                    UPDATE control_gestion.libros_diarios_consolidados
                    SET {", ".join(clauses)}
                    WHERE nombre_tercero = :prov
                """)
                res = db.execute(sql, p)
                cnt += res.rowcount
                print(f"   -> Proveedor {i.nombre_tercero}: {res.rowcount} filas")

        db.commit()
        return {"status": "success", "updated_rows": cnt}
    except Exception as e:
        db.rollback()
        print(f"❌ Error Update Provider: {e}")
        raise HTTPException(500, str(e))
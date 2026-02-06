from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional
from backend.database import get_db

router = APIRouter()

class ParametroInput(BaseModel):
    fecha_corte: str
    pais: str
    categoria: str
    concepto: str
    valor: float
    descripcion: Optional[str] = ""

# 1. OBTENER PARÁMETROS (Filtrados por Fecha y País)
@router.get("/params")
def get_financial_params(fecha_corte: str, pais: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        sql = """
            SELECT * FROM control_gestion.parametros_financieros 
            WHERE fecha_corte = :fecha
        """
        params = {"fecha": fecha_corte}
        
        if pais and pais != "Todos":
            sql += " AND pais = :pais"
            params["pais"] = pais
            
        sql += " ORDER BY categoria, concepto"
        
        result = db.execute(text(sql), params).fetchall()
        return [dict(row._mapping) for row in result]
    except Exception as e:
        raise HTTPException(500, str(e))

# 2. GUARDAR PARÁMETROS (UPSERT: Insertar o Actualizar)
@router.post("/params")
def save_financial_params(datos: List[ParametroInput], db: Session = Depends(get_db)):
    try:
        count = 0
        for item in datos:
            # Usamos ON CONFLICT para actualizar si ya existe ese concepto en esa fecha/pais
            sql = text("""
                INSERT INTO control_gestion.parametros_financieros 
                (fecha_corte, pais, categoria, concepto, valor, descripcion)
                VALUES (:fecha, :pais, :cat, :conc, :val, :desc)
                ON CONFLICT (fecha_corte, pais, categoria, concepto) 
                DO UPDATE SET 
                    valor = EXCLUDED.valor,
                    descripcion = EXCLUDED.descripcion;
            """)
            
            db.execute(sql, {
                "fecha": item.fecha_corte,
                "pais": item.pais,
                "cat": item.categoria,
                "conc": item.concepto,
                "val": item.valor,
                "desc": item.descripcion
            })
            count += 1
            
        db.commit()
        return {"status": "success", "processed": count}
    except Exception as e:
        db.rollback()
        print(f"❌ Error guardando params: {e}")
        raise HTTPException(500, detail=str(e))
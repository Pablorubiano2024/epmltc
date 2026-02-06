from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys

# Agregamos el directorio raíz al path para evitar errores de importación
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importamos los routers
from backend.routers import opex
from backend.routers import finance  # <--- NUEVO IMPORT

app = FastAPI(
    title="EPM Latam Trade Capital API",
    description="API para control de gestión, clasificación de gastos con IA y proyecciones financieras.",
    version="1.1.0"
)

# Configurar CORS (Permite que Streamlit hable con FastAPI)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REGISTRO DE RUTAS (ENDPOINTS) ---

# 1. Rutas de OPEX (Dashboard, IA, Explorador)
app.include_router(opex.router, prefix="/api/v1/opex", tags=["Opex"])

# 2. Rutas de FINANZAS (Gestor de Datos, Parámetros) - NUEVO
app.include_router(finance.router, prefix="/api/v1/finance", tags=["Finance"])

@app.get("/")
def read_root():
    return {
        "system": "EPM API", 
        "status": "online", 
        "modules": ["Opex Control", "Financial Planning"]
    }

if __name__ == "__main__":
    # Corre el servidor en el puerto 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
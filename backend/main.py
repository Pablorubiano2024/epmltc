from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# --- CAMBIO AQUÍ: Usamos la ruta completa 'backend.routers' ---
from backend.routers import opex 

app = FastAPI(
    title="EPM Latam Trade Capital API",
    description="API para control de gestión y clasificación de gastos con IA.",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir Rutas
app.include_router(opex.router, prefix="/api/v1/opex", tags=["Opex"])

@app.get("/")
def read_root():
    return {"system": "EPM API", "status": "active", "version": "1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
# backend/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

# Obtener credenciales
PG_HOST = os.getenv("PG_HOST")
PG_USER = os.getenv("PG_USER")
PG_PASS = os.getenv("PG_PASS")
PG_DB   = os.getenv("PG_DB")
PG_PORT = os.getenv("PG_PORT", "5432")

# Crear URL de conexión segura
DATABASE_URL = f"postgresql://{PG_USER}:{quote_plus(PG_PASS)}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# Crear el motor (Engine)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Crear la sesión local
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependencia para inyectar la sesión en cada endpoint
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
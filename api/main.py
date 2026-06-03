"""
main.py — Servidor FastAPI para la Plataforma de Datos Públicos Mexicanos.

Uso:
    python3 -m api.main              # Servidor en http://localhost:8000
    python3 -m api.main --port 8080  # Puerto personalizado
    python3 -m api.main --host 0.0.0.0  # Accesible desde la red

Documentación interactiva:
    http://localhost:8000/docs       # Swagger UI
    http://localhost:8000/redoc      # ReDoc
"""

import argparse
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import db
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa y cierra recursos de la BD."""
    # Startup: verificar que la BD existe
    try:
        total = db.conn.execute('SELECT COUNT(*) FROM registro').fetchone()[0]
        print(f"  ✅ BD principal: {total:,} registros")
        if db.conn_fts:
            print(f"  ✅ BD FTS5: disponible")
        else:
            print(f"  ⚠️  BD FTS5: no encontrada (buscar sin FTS5)")
    except FileNotFoundError as e:
        print(f"  ❌ {e}")
        print("  Ejecuta primero el pipeline de ingesta.")
        sys.exit(1)
    yield
    # Shutdown
    db.close()


app = FastAPI(
    title="Plataforma de Datos Públicos Mexicanos (PDP)",
    description="""
    API REST para consultar y exportar datos unificados de los Censos Nacionales de 
    Gobierno del INEGI (CNGF, CNGE, CNGMD) — 7.4M registros, 3 niveles de gobierno, 
    2011-2025.
    
    ## Endpoints principales
    
    * **`/api/info`** — Estadísticas generales del sistema
    * **`/api/tablas`** — Catálogo de fuentes disponibles
    * **`/api/consulta`** — Consulta parametrizada con filtros
    * **`/api/buscar`** — Búsqueda de texto completo (FTS5)
    * **`/api/exportar/{formato}`** — Exportación a CSV o JSON
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "PDP Project",
        "url": "https://github.com/usuario/pdp",
    },
    license_info={
        "name": "CC-BY-4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
    },
)

# CORS — abierto para desarrollo; restringir en producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# Rutas
app.include_router(router)


# ── Manejador global de errores ─────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": str(exc)},
    )


@app.get("/api/health", tags=["Sistema"])
async def health():
    """Health check detallado del sistema."""
    estado = {"ok": True, "componentes": {}}
    
    try:
        _ = db.conn.execute("SELECT 1").fetchone()
        estado["componentes"]["bd_principal"] = "ok"
    except Exception as e:
        estado["componentes"]["bd_principal"] = f"error: {e}"
        estado["ok"] = False
    
    try:
        db.conn_fts.execute("SELECT 1").fetchone()
        estado["componentes"]["bd_fts"] = "ok"
    except Exception:
        estado["componentes"]["bd_fts"] = "no_disponible"
    
    return estado


@app.get("/", tags=["Sistema"])
async def root():
    return {
        "nombre": "PDP API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "info": "/api/info",
            "tablas": "/api/tablas",
            "consulta": "/api/consulta",
            "buscar": "/api/buscar",
            "exportar": "/api/exportar/{csv|json}",
            "health": "/api/health",
        }
    }


# ── CLI ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PDP API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Puerto (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload en cambios")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()

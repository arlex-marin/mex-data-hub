"""
routes.py — Endpoints de la API REST de PDP.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from .database import db
from .models import Respuesta

router = APIRouter(prefix="/api", tags=["Datos"])


# ── Helpers ──────────────────────────────────────────────────

def _paginacion(pagina: int, por_pagina: int) -> tuple[int, int]:
    """Retorna (offset, limit)."""
    return (pagina - 1) * por_pagina, por_pagina


def _build_where(clauses: list[str], params: list[Any]) -> tuple[str, list]:
    """Construye WHERE a partir de cláusulas no vacías."""
    if not clauses:
        return "", []
    return "WHERE " + " AND ".join(clauses), params


def _ejecutar_consulta(sql: str, params: list) -> list:
    """Ejecuta una consulta SQL con manejo de errores."""
    try:
        return db.conn.execute(sql, params).fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en consulta: {e}")


def _contar(sql: str, params: list) -> int:
    """Ejecuta un COUNT con manejo de errores."""
    try:
        return db.conn.execute(sql, params).fetchone()[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en conteo: {e}")


def _serializar(rows: list) -> list[dict]:
    """Convierte filas sqlite3.Row a dicts con datos JSON parseados."""
    resultados = []
    for r in rows:
        d = dict(r)
        try:
            d["datos"] = json.loads(d.pop("datos_json"))
        except (json.JSONDecodeError, TypeError):
            d["datos"] = {}
        resultados.append(d)
    return resultados


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/info", response_model=Respuesta, tags=["Sistema"])
async def info():
    """Información del sistema y estadísticas generales."""
    total_reg = _contar("SELECT COUNT(*) FROM registro", [])
    total_cat = _contar("SELECT COUNT(*) FROM catalogo", [])
    censos = [r[0] for r in _ejecutar_consulta(
        "SELECT DISTINCT censo FROM catalogo ORDER BY censo", [])]
    años = [r[0] for r in _ejecutar_consulta(
        "SELECT DISTINCT año FROM catalogo ORDER BY año", [])]

    return Respuesta(
        datos=[{
            "estatus": "operacional",
            "version": "1.0.0",
            "bd_principal": str(db.conn.execute("PRAGMA database_list").fetchone()[2]),
            "bd_fts": "disponible" if db.conn_fts else "no disponible",
            "total_registros": total_reg,
            "total_fuentes": total_cat,
            "censos_disponibles": censos,
            "años_disponibles": años,
        }],
        total=1
    )


@router.get("/tablas", response_model=Respuesta, tags=["Catálogo"])
async def listar_tablas(
    censo: str | None = Query(None, description="Filtrar por censo (CNGF, CNGE, CNGMD)"),
    nivel: str | None = Query(None, description="Filtrar por nivel (federal, estatal, municipal)"),
    año: int | None = Query(None, description="Filtrar por año de publicación"),
    modulo: str | None = Query(None, description="Filtrar por módulo (contiene búsqueda parcial)"),
    tipo_fuente: str | None = Query(None, description="Filtrar por tipo (DBF, XLSX)"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=500),
):
    """Lista las fuentes disponibles con metadatos."""
    clauses: list[str] = []
    params: list[Any] = []

    if censo:
        clauses.append("censo = ?")
        params.append(censo.upper())
    if nivel:
        clauses.append("nivel = ?")
        params.append(nivel.lower())
    if año:
        clauses.append("año = ?")
        params.append(año)
    if modulo:
        clauses.append("modulo LIKE ?")
        params.append(f"%{modulo}%")
    if tipo_fuente:
        clauses.append("tipo_fuente = ?")
        params.append(tipo_fuente.upper())

    where, params = _build_where(clauses, params)
    offset, limit = _paginacion(pagina, por_pagina)

    count = db.conn.execute(
        f"SELECT COUNT(*) FROM catalogo {where}", params
    ).fetchone()[0]

    rows = db.conn.execute(
        f"SELECT * FROM catalogo {where} ORDER BY censo, año, modulo LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()

    return Respuesta(
        datos=[dict(r) for r in rows],
        total=count,
        pagina=pagina,
        por_pagina=por_pagina,
    )


@router.get("/consulta", response_model=Respuesta, tags=["Datos"])
async def consultar(
    censo: str | None = Query(None, description="Filtrar por censo"),
    nivel: str | None = Query(None, description="Filtrar por nivel"),
    año: int | None = Query(None, description="Filtrar por año de publicación"),
    periodo: int | None = Query(None, description="Filtrar por período del censo"),
    modulo: str | None = Query(None, description="Filtrar por módulo (contiene)"),
    entidad: str | None = Query(None, description="Filtrar por entidad federativa (contiene)"),
    clave_geo: str | None = Query(None, description="Filtrar por clave geográfica exacta"),
    municipio: str | None = Query(None, description="Filtrar por municipio (contiene)"),
    tipo_fuente: str | None = Query(None, description="Filtrar por tipo de fuente"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(100, ge=1, le=1000),
):
    """Consulta datos con filtros combinados."""
    clauses: list[str] = []
    params: list[Any] = []

    if censo:
        clauses.append("c.censo = ?")
        params.append(censo.upper())
    if nivel:
        clauses.append("c.nivel = ?")
        params.append(nivel.lower())
    if año:
        clauses.append("c.año = ?")
        params.append(año)
    if periodo:
        clauses.append("c.periodo = ?")
        params.append(periodo)
    if modulo:
        clauses.append("c.modulo LIKE ?")
        params.append(f"%{modulo}%")
    if entidad:
        clauses.append("r.entidad LIKE ?")
        params.append(f"%{entidad}%")
    if clave_geo:
        clauses.append("r.clave_geo = ?")
        params.append(clave_geo)
    if municipio:
        clauses.append("r.municipio LIKE ?")
        params.append(f"%{municipio}%")
    if tipo_fuente:
        clauses.append("c.tipo_fuente = ?")
        params.append(tipo_fuente.upper())

    where, params = _build_where(clauses, params)
    offset, limit = _paginacion(pagina, por_pagina)

    count = _contar(
        f"SELECT COUNT(*) FROM registro r JOIN catalogo c ON r.fuente_id = c.id {where}",
        params,
    )

    rows = _ejecutar_consulta(
        f"""SELECT r.id, c.censo, c.nivel, c.año, c.periodo, c.modulo,
                  r.clave_geo, r.entidad, r.municipio, r.datos_json
           FROM registro r
           JOIN catalogo c ON r.fuente_id = c.id
           {where}
           ORDER BY c.censo, c.año, r.id
           LIMIT ? OFFSET ?""",
        params + [limit, offset],
    )

    return Respuesta(
        datos=_serializar(rows),
        total=count,
        pagina=pagina,
        por_pagina=por_pagina,
    )


@router.get("/buscar", response_model=Respuesta, tags=["Búsqueda"])
async def buscar(
    q: str = Query(..., min_length=1, max_length=200, description="Texto a buscar en FTS5"),
    censo: str | None = Query(None, description="Filtrar por censo"),
    modulo: str | None = Query(None, description="Filtrar por módulo"),
    entidad: str | None = Query(None, description="Filtrar por entidad"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
    """Búsqueda de texto completo sobre todos los datos usando FTS5."""
    if not db.conn_fts:
        return Respuesta(ok=False, error="BD FTS5 no disponible. Construir con: python3 optimizar_bd.py")

    # Limpiar y preparar query FTS5
    q_clean = q.replace('"', ' ').strip()
    # Si contiene espacios, activar modo frase
    if ' ' in q_clean:
        fts_query = f'"{q_clean}"'
    else:
        fts_query = f'{q_clean}*'

    clauses: list[str] = ["registro_fts MATCH ?"]
    params: list[Any] = [fts_query]

    if censo:
        clauses.append("censo = ?")
        params.append(censo.upper())
    if modulo:
        clauses.append("modulo = ?")
        params.append(modulo)
    if entidad:
        clauses.append("entidad LIKE ?")
        params.append(f"%{entidad}%")

    where = " AND ".join(clauses)
    offset, limit = _paginacion(pagina, por_pagina)

    count = db.conn_fts.execute(
        f"SELECT COUNT(*) FROM registro_fts WHERE {where}", params
    ).fetchone()[0]

    rows = db.conn_fts.execute(
        f"""
        SELECT rowid, texto_busqueda, censo, modulo, entidad
        FROM registro_fts
        WHERE {where}
        ORDER BY rank
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    ).fetchall()

    return Respuesta(
        datos=[dict(r) for r in rows],
        total=count,
        pagina=pagina,
        por_pagina=por_pagina,
    )


@router.get("/exportar/{formato}", tags=["Exportación"])
async def exportar(
    formato: str,
    censo: str | None = Query(None),
    año: int | None = Query(None),
    modulo: str | None = Query(None),
    fuente_id: int | None = Query(None),
    entidad: str | None = Query(None),
    max_registros: int = Query(10000, ge=1, le=100000),
):
    """Exporta datos filtrados a CSV o JSON.
    
    Descarga un archivo con los datos filtrados. Para JSON, los campos
    específicos de cada fuente se incluyen anidados en la clave 'datos'.
    """
    if formato not in ("csv", "json"):
        raise HTTPException(
            status_code=400,
            detail=f"Formato '{formato}' no soportado. Usar 'csv' o 'json'."
        )

    clauses: list[str] = []
    params: list[Any] = []

    if censo:
        clauses.append("c.censo = ?")
        params.append(censo.upper())
    if año:
        clauses.append("c.año = ?")
        params.append(año)
    if modulo:
        clauses.append("c.modulo LIKE ?")
        params.append(f"%{modulo}%")
    if fuente_id:
        clauses.append("r.fuente_id = ?")
        params.append(fuente_id)
    if entidad:
        clauses.append("r.entidad LIKE ?")
        params.append(f"%{entidad}%")

    where, params = _build_where(clauses, params)

    rows = db.conn.execute(
        f"""
        SELECT r.id, c.censo, c.nivel, c.año, c.periodo, c.modulo,
               r.clave_geo, r.entidad, r.municipio, r.datos_json
        FROM registro r
        JOIN catalogo c ON r.fuente_id = c.id
        {where}
        ORDER BY c.censo, c.año, r.id
        LIMIT ?
        """,
        params + [max_registros],
    ).fetchall()

    if formato == "json":
        return PlainTextResponse(
            content=json.dumps(
                _serializar(rows), ensure_ascii=False, indent=2, default=str
            ),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=pdp_export.json"},
        )

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "censo", "nivel", "año", "periodo", "modulo",
                      "clave_geo", "entidad", "municipio", "datos"])
    for r in rows:
        writer.writerow([
            r["id"], r["censo"], r["nivel"], r["año"], r["periodo"],
            r["modulo"], r["clave_geo"], r["entidad"], r["municipio"],
            r["datos_json"],
        ])

    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=pdp_export.csv"},
    )

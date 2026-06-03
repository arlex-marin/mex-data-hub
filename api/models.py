"""
models.py — Modelos Pydantic para la API REST de PDP.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Respuestas genéricas ─────────────────────────────────────

class Respuesta(BaseModel):
    ok: bool = True
    datos: list[dict[str, Any]] = []
    total: int = 0
    pagina: int = 1
    por_pagina: int = 100
    error: Optional[str] = None


class ErrorRespuesta(BaseModel):
    ok: bool = False
    error: str


# ── Parámetros de consulta ───────────────────────────────────

class FiltrosTablas(BaseModel):
    censo: Optional[str] = None
    nivel: Optional[str] = None
    año: Optional[int] = None
    modulo: Optional[str] = None
    tipo_fuente: Optional[str] = None
    pagina: int = Field(default=1, ge=1)
    por_pagina: int = Field(default=50, ge=1, le=500)


class FiltrosConsulta(BaseModel):
    censo: Optional[str] = None
    nivel: Optional[str] = None
    año: Optional[int] = None
    periodo: Optional[int] = None
    modulo: Optional[str] = None
    entidad: Optional[str] = None
    clave_geo: Optional[str] = None
    municipio: Optional[str] = None
    tipo_fuente: Optional[str] = None
    pagina: int = Field(default=1, ge=1)
    por_pagina: int = Field(default=100, ge=1, le=1000)


class FiltrosBusqueda(BaseModel):
    q: str = Field(..., min_length=1, max_length=200)
    censo: Optional[str] = None
    modulo: Optional[str] = None
    entidad: Optional[str] = None
    pagina: int = Field(default=1, ge=1)
    por_pagina: int = Field(default=20, ge=1, le=100)


class FiltrosExportar(BaseModel):
    formato: str = Field(..., pattern=r'^(csv|json)$')
    censo: Optional[str] = None
    año: Optional[int] = None
    modulo: Optional[str] = None
    fuente_id: Optional[int] = None
    entidad: Optional[str] = None
    max_registros: int = Field(default=10000, ge=1, le=100000)


# ── Información del sistema ──────────────────────────────────

class InfoSistema(BaseModel):
    estatus: str = "operacional"
    version: str = "1.0.0"
    bd_principal: str
    bd_fts: Optional[str] = None
    total_registros: int = 0
    total_fuentes: int = 0
    censos_disponibles: list[str] = []
    años_disponibles: list[int] = []

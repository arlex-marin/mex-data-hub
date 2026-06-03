#!/usr/bin/env python3
"""
optimizar_bd.py — Fase 0.4: Optimización de la base de datos.

Lee la BD actual (datos_pdp.db ~10.7 GB) y produce:

1. datos_pdp.db  (~3 GB) — Base principal optimizada
   - Compact JSON (separators, sin espacios)
   - Sin texto_busqueda (eliminada, duplicada en FTS5)
   - Índices adicionales: (censo, año, modulo), (entidad), (clave_geo)
   - Vista periodo para resolver año_publicacion → periodo

2. datos_pdp_fts.db (~3 GB) — Índice de búsqueda FTS5 (archivo separado)
   - Self-contained FTS5 (content='')
   - Reconstruible desde datos_pdp.db

Meta: BD principal < 4 GB para distribución en Zenodo.
"""

import json
import os
import sqlite3
import time
from pathlib import Path


# ── Rutas ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_VIEJA = BASE_DIR / 'data' / 'datos_pdp.db'
DB_NUEVA = BASE_DIR / 'data' / 'datos_pdp_opt.db'
DB_FTS = BASE_DIR / 'data' / 'datos_pdp_fts.db'


# ── Esquema optimizado ──────────────────────────────────────

ESQUEMA_PRINCIPAL = """
-- Catálogo de fuentes (igual que antes)
CREATE TABLE IF NOT EXISTS catalogo (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    censo       TEXT NOT NULL,
    nivel       TEXT NOT NULL,
    año         INTEGER NOT NULL,
    periodo     INTEGER,
    modulo      TEXT NOT NULL,
    tipo_fuente TEXT NOT NULL,
    nombre_tabla TEXT NOT NULL,
    archivo_origen TEXT,
    total_registros INTEGER DEFAULT 0,
    total_campos    INTEGER DEFAULT 0,
    fecha_ingesta  TEXT DEFAULT (datetime('now'))
);

-- Registros optimizados: sin texto_busqueda, compact JSON
CREATE TABLE IF NOT EXISTS registro (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_id   INTEGER NOT NULL REFERENCES catalogo(id),
    datos_json  TEXT NOT NULL,
    clave_geo   TEXT,
    entidad     TEXT,
    municipio   TEXT
);

-- Índices para consultas comunes
CREATE INDEX IF NOT EXISTS idx_catalogo_censo  ON catalogo(censo);
CREATE INDEX IF NOT EXISTS idx_catalogo_modulo ON catalogo(modulo);
CREATE INDEX IF NOT EXISTS idx_catalogo_anio   ON catalogo(año);
CREATE INDEX IF NOT EXISTS idx_registro_fuente ON registro(fuente_id);
CREATE INDEX IF NOT EXISTS idx_registro_entidad ON registro(entidad);
CREATE INDEX IF NOT EXISTS idx_registro_clave_geo ON registro(clave_geo);

-- Vista para resolver año_publicacion → periodo del censo
CREATE VIEW IF NOT EXISTS vista_periodo AS
SELECT 
    r.id,
    c.censo,
    c.año AS año_publicacion,
    COALESCE(c.periodo, c.año - 1) AS periodo,
    c.modulo,
    c.nivel,
    r.entidad,
    r.municipio,
    r.clave_geo,
    r.datos_json
FROM registro r
JOIN catalogo c ON r.fuente_id = c.id;

-- Vista consolidada con año_publicacion y periodo
CREATE VIEW IF NOT EXISTS vista_consulta AS
SELECT 
    r.id,
    c.censo,
    c.nivel,
    c.año AS año_publicacion,
    COALESCE(c.periodo, c.año - 1) AS periodo,
    c.modulo,
    c.tipo_fuente,
    r.entidad,
    r.municipio,
    r.clave_geo,
    r.datos_json
FROM registro r
JOIN catalogo c ON r.fuente_id = c.id;
"""


ESQUEMA_FTS = """
-- Índice FTS5 autocontenido (content='')
-- Separa el texto de búsqueda del contenido principal
-- para reducir el tamaño de la BD principal.
CREATE VIRTUAL TABLE IF NOT EXISTS registro_fts USING fts5(
    texto_busqueda,
    censo,
    modulo,
    entidad,
    content='',
    tokenize='unicode61'
);
"""


# ── Migración ────────────────────────────────────────────────

def _generar_texto_busqueda(record: dict, censo: str, modulo: str) -> str:
    """Genera texto de búsqueda compacto para FTS5."""
    partes = [censo, modulo]
    for k, v in record.items():
        if k.startswith('_'):
            continue
        if v is not None:
            partes.append(f"{k}: {v}")
    return ' | '.join(str(p) for p in partes)


def migrar():
    """Migra datos de la BD vieja a la nueva optimizada.
    
    Fase 1: crea BD principal optimizada (sin FTS5).
    Fase 2: elimina BD vieja, crea BD FTS5 aparte.
    """
    
    if not DB_VIEJA.exists():
        print(f"❌ No existe BD origen: {DB_VIEJA}")
        return
    
    size_vieja = DB_VIEJA.stat().st_size
    
    print(f"{'='*60}")
    print(f"FASE 0.4 — Optimización de Base de Datos")
    print(f"{'='*60}")
    print(f"  Origen:  {DB_VIEJA.name} ({size_vieja/1024/1024/1024:.1f} GB)")
    print(f"  Destino: {DB_NUEVA.name}")
    print(f"  FTS5:    {DB_FTS.name}")
    print()
    
    conn_vieja = sqlite3.connect(str(DB_VIEJA))
    conn_vieja.row_factory = sqlite3.Row
    
    # === FASE 1: BD principal optimizada ===
    if DB_NUEVA.exists():
        DB_NUEVA.unlink()
    
    conn_nueva = sqlite3.connect(str(DB_NUEVA))
    conn_nueva.execute("PRAGMA journal_mode=WAL")
    conn_nueva.execute("PRAGMA synchronous=OFF")
    conn_nueva.execute("PRAGMA cache_size=-8000000")
    conn_nueva.executescript(ESQUEMA_PRINCIPAL)
    
    inicio = time.time()
    
    # Migrar catálogo
    print("📋 Migrando catálogo...")
    catalogo_rows = conn_vieja.execute("""
        SELECT id, censo, nivel, año, periodo, modulo, tipo_fuente, 
               nombre_tabla, archivo_origen, total_registros, total_campos
        FROM catalogo ORDER BY id
    """).fetchall()
    
    mapa_fuente = {}
    for row in catalogo_rows:
        cur = conn_nueva.execute("""
            INSERT INTO catalogo (censo, nivel, año, periodo, modulo, tipo_fuente,
                                  nombre_tabla, archivo_origen, total_registros, total_campos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['censo'], row['nivel'], row['año'], row['periodo'],
            row['modulo'], row['tipo_fuente'], row['nombre_tabla'],
            row['archivo_origen'], row['total_registros'], row['total_campos']
        ))
        mapa_fuente[row['id']] = cur.lastrowid
    
    conn_nueva.commit()
    print(f"  ✅ {len(catalogo_rows)} fuentes migradas")
    
    # Migrar registros en lote
    print("📦 Migrando registros (compact JSON, sin texto_busqueda)...")
    
    batch_size = 5000
    total = 0
    last_id = 0
    
    while True:
        rows = conn_vieja.execute("""
            SELECT r.id, r.fuente_id, r.datos_json, r.clave_geo, r.entidad, r.municipio
            FROM registro r
            WHERE r.id > ?
            ORDER BY r.id
            LIMIT ?
        """, (last_id, batch_size)).fetchall()
        
        if not rows:
            break
        
        batch = []
        for row in rows:
            fuente_nuevo_id = mapa_fuente.get(row['fuente_id'])
            if fuente_nuevo_id is None:
                continue
            
            # Compact JSON
            try:
                datos = json.loads(row['datos_json'])
                json_compacto = json.dumps(datos, ensure_ascii=False, default=str, separators=(',', ':'))
            except (json.JSONDecodeError, TypeError):
                json_compacto = row['datos_json']
            
            batch.append((
                fuente_nuevo_id,
                json_compacto,
                row['clave_geo'],
                row['entidad'],
                row['municipio']
            ))
        
        conn_nueva.executemany("""
            INSERT INTO registro (fuente_id, datos_json, clave_geo, entidad, municipio)
            VALUES (?, ?, ?, ?, ?)
        """, batch)
        conn_nueva.commit()
        
        total += len(rows)
        last_id = rows[-1]['id']
        
        if total % 50000 == 0:
            pct = total * 100 // 7400215
            print(f"  Progreso: {total:>8,} / 7,400,215 ({pct}%)")
    
    conn_vieja.close()
    conn_nueva.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn_nueva.close()
    
    duracion = time.time() - inicio
    size_nueva = DB_NUEVA.stat().st_size
    
    print(f"\n✅ FASE 1 COMPLETA — BD principal creada")
    print(f"   Tamaño: {size_nueva/1024/1024/1024:.1f} GB")
    print(f"   Duración: {duracion:.0f}s")
    print()
    
    # === FASE 2: Eliminar BD vieja, crear FTS5 ===
    print("🗑️  Eliminando BD vieja para liberar espacio...")
    DB_VIEJA.unlink()
    print(f"   Liberados {size_vieja/1024/1024/1024:.1f} GB")
    print()
    
    print("🔍 Construyendo índice FTS5 (archivo aparte)...")
    _construir_fts(conn_nueva=None)  # Se conecta a DB_NUEVA
    
    # === Final: renombrar ===
    print(f"\n{'='*60}")
    print(f"OPTIMIZACIÓN COMPLETADA")
    print(f"{'='*60}")
    _reportar()


def _construir_fts(conn_nueva=None):
    """Construye BD FTS5 aparte desde la BD principal optimizada."""
    if DB_FTS.exists():
        DB_FTS.unlink()
    
    conn_principal = sqlite3.connect(str(DB_NUEVA))
    conn_principal.row_factory = sqlite3.Row
    conn_principal.execute("PRAGMA synchronous=OFF")
    
    conn_fts = sqlite3.connect(str(DB_FTS))
    conn_fts.execute("PRAGMA synchronous=OFF")
    conn_fts.execute("PRAGMA cache_size=-4000000")
    conn_fts.executescript(ESQUEMA_FTS)
    
    inicio = time.time()
    batch_size = 5000
    total = 0
    last_id = 0
    
    print("  Generando texto de búsqueda para FTS5...")
    
    while True:
        rows = conn_principal.execute("""
            SELECT r.id, r.datos_json, r.entidad, c.censo, c.modulo
            FROM registro r
            JOIN catalogo c ON r.fuente_id = c.id
            WHERE r.id > ?
            ORDER BY r.id
            LIMIT ?
        """, (last_id, batch_size)).fetchall()
        
        if not rows:
            break
        
        batch = []
        for row in rows:
            try:
                datos = json.loads(row['datos_json'])
            except json.JSONDecodeError:
                datos = {}
            
            censo = row['censo'] or ''
            modulo = row['modulo'] or ''
            texto = _generar_texto_busqueda(datos, censo, modulo)
            
            batch.append((
                row['id'],
                texto,
                censo,
                modulo,
                row['entidad'] or ''
            ))
        
        conn_fts.executemany("""
            INSERT INTO registro_fts(rowid, texto_busqueda, censo, modulo, entidad)
            VALUES (?, ?, ?, ?, ?)
        """, batch)
        conn_fts.commit()
        
        total += len(rows)
        last_id = rows[-1]['id']
        
        if total % 100000 == 0:
            print(f"    Progreso FTS5: {total:>8,} / 7,400,215")
    
    conn_fts.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn_fts.close()
    conn_principal.close()
    
    size_fts = DB_FTS.stat().st_size
    print(f"  ✅ FTS5 construido: {size_fts/1024/1024/1024:.1f} GB ({total:,} filas)")
    print(f"     Duración: {time.time() - inicio:.0f}s")


def _reportar():
    """Reporta estadísticas finales de las BDs optimizadas."""
    size_nueva = DB_NUEVA.stat().st_size if DB_NUEVA.exists() else 0
    size_fts = DB_FTS.stat().st_size if DB_FTS.exists() else 0
    
    try:
        conn = sqlite3.connect(str(DB_NUEVA))
        reg_count = conn.execute("SELECT COUNT(*) FROM registro").fetchone()[0]
        cat_count = conn.execute("SELECT COUNT(*) FROM catalogo").fetchone()[0]
        conn.close()
    except:
        reg_count = 0
        cat_count = 0
    
    try:
        conn = sqlite3.connect(str(DB_FTS))
        fts_count = conn.execute("SELECT COUNT(*) FROM registro_fts").fetchone()[0]
        conn.close()
    except:
        fts_count = 0
    
    total_combinado = size_nueva + size_fts
    vieja_size = 0  # ya no existe
    
    print(f"  Catálogo:    {cat_count:,} fuentes")
    print(f"  Registros:   {reg_count:,}")
    print(f"  FTS5 filas:  {fts_count:,}")
    print()
    print(f"  {'':30s} {'TAMAÑO':>10s}")
    print(f"  {'-'*30} {'-'*10}")
    print(f"  {'BD principal (datos_pdp.db)':30s} {size_nueva/1024/1024/1024:>9.1f} GB")
    print(f"  {'BD FTS5 (datos_pdp_fts.db)':30s} {size_fts/1024/1024/1024:>9.1f} GB")
    print(f"  {'Total':30s} {total_combinado/1024/1024/1024:>9.1f} GB")
    print()
    print(f"✅ Optimización completada.")
    print(f"   Principal: {DB_NUEVA}")
    print(f"   FTS5:      {DB_FTS}")


if __name__ == '__main__':
    migrar()

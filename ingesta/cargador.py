"""
cargador.py — Carga datos parseados a SQLite + FTS5 (esquema optimizado v2).

Lee los archivos JSONL de staging_dbf/ y staging_xlsx/ y los carga
en una base de datos SQLite unificada con índices y búsqueda FTS5.

Esquema optimizado (v2):
  - catalogo: metadatos de cada fuente (censo, año, módulo, nivel, tabla)
  - registro: datos individuales con JSON compacto, clave_geo, entidad, municipio
  - vista_periodo: resuelve año_publicación → periodo del censo
  - registro_fts (BD aparte datos_pdp_fts.db): FTS5 sobre datos_json

Mejoras respecto a v1:
  - Compact JSON (separators=(',',':')): ~15% menos tamaño
  - Sin texto_busqueda en registro (evita duplicación con FTS5)
  - FTS5 en archivo separado (reconstruible, descarga opcional)
  - Vistas para resolver discrepancia año publicación vs período censo
"""

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ── Mapeo censo → nivel ──────────────────────────────────────
CENSO_NIVEL = {
    'cngf': 'federal',
    'cnge': 'estatal',
    'cngmd': 'municipal',
}

# Mapeo año_publicacion → periodo (año que describen los datos)
CENSO_PERIODO = {
    'cngf':  {2017: 2016, 2018: 2017, 2019: 2018,
              2020: 2019, 2021: 2020, 2022: 2021, 2023: 2022, 2024: 2023, 2025: 2024},
    'cnge':  {2021: 2020, 2022: 2021, 2023: 2022, 2024: 2023, 2025: 2024},
    'cngmd': {2011: 2010, 2013: 2012, 2015: 2014, 2017: 2016, 2019: 2018,
              2021: 2020, 2023: 2022, 2025: 2024},
}


# ── Extracción de claves geográficas ──────────────────────────

def _extraer_clave_geo(record: dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Intenta extraer clave geográfica, entidad y municipio de un registro.
    
    Busca campos comunes como:
    - clave_geo, cvegeo, clave, UB_GEO, etc.
    - entidad, estado, Entidad federativa, etc.
    - municipio, Municipio, etc.
    """
    clave = None
    entidad = None
    municipio = None
    
    for k, v in record.items():
        if v is None:
            continue
        k_lower = k.lower().strip()
        v_str = str(v).strip()
        
        # Clave geográfica
        if any(x in k_lower for x in ['clave_geo', 'cvegeo', 'clave_geográfica', 'clave_geografica', 'ub_geo']):
            if re.match(r'^\d+$', v_str) and len(v_str) >= 3:
                clave = v_str
        # O códigos de estado/municipio en primera posición sin header keyword
        if clave is None and k_lower == 'clave':
            if re.match(r'^\d+$', v_str) and len(v_str) >= 3:
                clave = v_str
        
        # Entidad federativa
        if any(x in k_lower for x in ['entidad']):
            if len(v_str) > 3 and not re.match(r'^\d+$', v_str):
                entidad = v_str
        
        # Municipio
        if any(x in k_lower for x in ['municipio']):
            if len(v_str) > 3 and not re.match(r'^\d+$', v_str):
                municipio = v_str
                
        # Estado (si no se encontró entidad)
        if entidad is None and k_lower in ('estado', 'state'):
            if len(v_str) > 3:
                entidad = v_str
    
    return clave, entidad, municipio


def _extraer_censo_de_nombre(nombre_tabla: str) -> Optional[str]:
    """Extrae censo del nombre de tabla: cngf_2017_... → cngf"""
    m = re.match(r'(cng[fe]|cngmd)_', nombre_tabla)
    return m.group(1) if m else None


def _extraer_anio_de_nombre(nombre_tabla: str) -> Optional[int]:
    """Extrae año del nombre de tabla: cngf_2017_... → 2017"""
    m = re.search(r'_(\d{4})_', nombre_tabla)
    return int(m.group(1)) if m else None


def _extraer_modulo_de_nombre(nombre_tabla: str) -> Optional[str]:
    """Extrae módulo del nombre."""
    parts = nombre_tabla.split('_')
    if len(parts) >= 3:
        # Skip censo and year
        modulo_parts = parts[2:]
        # Remove trailing type markers
        TIPO_MARKERS = {'microdatos', 'tabulados', 'marco', 'conceptual'}
        while modulo_parts and modulo_parts[-1] in TIPO_MARKERS:
            modulo_parts = modulo_parts[:-1]
        # Remove DBF table suffix (after __)
        clean = '_'.join(modulo_parts).split('__')[0]
        return clean if clean else None
    return None


# ── Creación de esquema ──────────────────────────────────────

ESQUEMA_SQL = """
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

CREATE TABLE IF NOT EXISTS registro (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_id   INTEGER NOT NULL REFERENCES catalogo(id),
    datos_json  TEXT NOT NULL,
    clave_geo   TEXT,
    entidad     TEXT,
    municipio   TEXT
);

CREATE INDEX IF NOT EXISTS idx_catalogo_censo  ON catalogo(censo);
CREATE INDEX IF NOT EXISTS idx_catalogo_modulo ON catalogo(modulo);
CREATE INDEX IF NOT EXISTS idx_catalogo_anio   ON catalogo(año);
CREATE INDEX IF NOT EXISTS idx_registro_fuente ON registro(fuente_id);
CREATE INDEX IF NOT EXISTS idx_registro_entidad ON registro(entidad);
CREATE INDEX IF NOT EXISTS idx_registro_clave_geo ON registro(clave_geo);

-- Vistas para resolver año_publicación → periodo del censo
CREATE VIEW IF NOT EXISTS vista_periodo AS
SELECT 
    r.id,
    c.censo,
    c.año AS año_publicacion,
    COALESCE(c.periodo, c.año - 1) AS periodo,
    c.modulo, c.nivel,
    r.entidad, r.municipio, r.clave_geo, r.datos_json
FROM registro r
JOIN catalogo c ON r.fuente_id = c.id;

CREATE VIEW IF NOT EXISTS vista_consulta AS
SELECT 
    r.id, c.censo, c.nivel,
    c.año AS año_publicacion,
    COALESCE(c.periodo, c.año - 1) AS periodo,
    c.modulo, c.tipo_fuente,
    r.entidad, r.municipio, r.clave_geo, r.datos_json
FROM registro r
JOIN catalogo c ON r.fuente_id = c.id;
"""


# ── Carga ────────────────────────────────────────────────────

class CargadorSQLite:
    """
    Carga datos desde archivos JSONL (staging) a SQLite.
    
    Uso:
        cargador = CargadorSQLite('datos.db')
        cargador.cargar_todo('data/staging_dbf', 'data/staging_xlsx')
        cargador.cerrar()
    """
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=OFF")
        self.conn.execute("PRAGMA cache_size=-4000000")  # ~4GB cache
        self.conn.row_factory = sqlite3.Row
        
        self._crear_esquema()
        self._stats = {
            'fuentes': 0,
            'registros': 0,
            'tiempo': 0,
        }
    
    def _crear_esquema(self):
        self.conn.executescript(ESQUEMA_SQL)
        self.conn.commit()
    
    def _registrar_fuente(self, metadatos: dict) -> int:
        """Inserta una fuente en el catálogo y retorna su ID."""
        cursor = self.conn.execute("""
            INSERT INTO catalogo (censo, nivel, año, periodo, modulo, tipo_fuente,
                                  nombre_tabla, archivo_origen, total_registros, total_campos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metadatos.get('censo', '').upper(),
            metadatos.get('nivel', ''),
            metadatos.get('año', 0),
            metadatos.get('periodo'),
            metadatos.get('modulo', ''),
            metadatos.get('tipo_fuente', ''),
            metadatos.get('nombre_tabla', ''),
            metadatos.get('archivo_origen', ''),
            metadatos.get('total_registros', 0),
            metadatos.get('total_campos', 0),
        ))
        return cursor.lastrowid
    
    def _generar_texto_busqueda(self, record: dict, censo: str, modulo: str) -> str:
        """Genera texto de búsqueda concatenando todos los valores."""
        partes = [censo, modulo]
        for k, v in record.items():
            if k.startswith('_'):
                continue
            if v is not None:
                partes.append(f"{k}: {v}")
        return ' | '.join(str(p) for p in partes)
    
    def cargar_jsonl(self, jsonl_path: Path, tipo_fuente: str) -> dict:
        """
        Carga un archivo JSONL a la base de datos.
        
        Args:
            jsonl_path: Ruta al archivo .jsonl
            tipo_fuente: 'DBF', 'CSV', o 'XLSX'
        
        Returns:
            Dict con estadísticas de carga
        """
        nombre_archivo = jsonl_path.stem
        meta_path = jsonl_path.with_name(jsonl_path.stem.replace('.jsonl', '') + '.meta.json')
        
        # Leer metadatos si existen
        metadatos = {}
        if meta_path.exists():
            with open(meta_path) as f:
                metadatos = json.load(f)
        
        censo = metadatos.get('censo', '') or (metadatos.get('nombre_archivo', '').split('_')[0] if '_' in metadatos.get('nombre_archivo', '') else '')
        año = metadatos.get('año', 0)
        modulo = metadatos.get('modulo', '')
        total_campos = len(metadatos.get('campos', []))
        
        # Si no hay metadatos, extraer del nombre
        if not censo:
            censo = _extraer_censo_de_nombre(nombre_archivo) or ''
        if not año:
            año = _extraer_anio_de_nombre(nombre_archivo) or 0
        if not modulo:
            modulo = _extraer_modulo_de_nombre(nombre_archivo) or ''
        
        nivel = CENSO_NIVEL.get(censo.lower(), 'desconocido')
        periodo = CENSO_PERIODO.get(censo.lower(), {}).get(int(año)) if año else None
        
        # Leer registros
        registros = []
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        registros.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        # Registrar fuente en catálogo
        fuente_id = self._registrar_fuente({
            'censo': censo,
            'nivel': nivel,
            'año': año,
            'periodo': periodo,
            'modulo': modulo,
            'tipo_fuente': tipo_fuente,
            'nombre_tabla': nombre_archivo,
            'archivo_origen': nombre_archivo,
            'total_registros': len(registros),
            'total_campos': total_campos,
        })
        
        # Insertar registros en lote (compact JSON, sin texto_busqueda)
        batch = []
        for reg in registros:
            clave_geo, entidad, municipio = _extraer_clave_geo(reg)
            # Compact JSON: separadores sin espacios, reduce ~15% tamaño
            datos_str = json.dumps(reg, ensure_ascii=False, default=str, separators=(',', ':'))
            batch.append((fuente_id, datos_str, clave_geo, entidad, municipio))
        
        if batch:
            self.conn.executemany("""
                INSERT INTO registro (fuente_id, datos_json, clave_geo, entidad, municipio)
                VALUES (?, ?, ?, ?, ?)
            """, batch)
        
        self.conn.commit()
        
        return {
            'fuente_id': fuente_id,
            'censo': censo,
            'año': año,
            'modulo': modulo,
            'registros': len(registros),
            'campos': total_campos,
        }
    
    def cargar_directorio(self, dir_path: Path, tipo_fuente: str) -> List[dict]:
        """Carga todos los archivos .jsonl de un directorio."""
        resultados = []
        jsonl_files = sorted(dir_path.glob('*.jsonl'))
        
        for i, jf in enumerate(jsonl_files, 1):
            # Saltar archivos .meta.json y resumen
            if jf.name.endswith('.meta.json') or jf.name == 'resumen_ingesta.json':
                continue
            
            try:
                res = self.cargar_jsonl(jf, tipo_fuente)
                resultados.append(res)
                self._stats['fuentes'] += 1
                self._stats['registros'] += res['registros']
                
                print(f"  [{i:3d}/{len(jsonl_files)}] ✅ {jf.name} → {res['registros']} reg (fuente #{res['fuente_id']})")
                
            except Exception as e:
                print(f"  [{i:3d}/{len(jsonl_files)}] ❌ {jf.name} — {e}")
        
        return resultados
    
    def cargar_todo(self, dbf_dir: Path, xlsx_dir: Path, fts_path: Path = None):
        """Carga datos DBF y XLSX en secuencia.
        
        Args:
            dbf_dir: Directorio con JSONL de DBF/CSV
            xlsx_dir: Directorio con JSONL de XLSX
            fts_path: Si se especifica, construye BD FTS5 aparte en esta ruta
        """
        inicio = time.time()
        
        print(f"\n📂 Cargando DBF/CSV desde: {dbf_dir}")
        self.cargar_directorio(dbf_dir, 'DBF')
        
        print(f"\n📂 Cargando XLSX desde: {xlsx_dir}")
        self.cargar_directorio(xlsx_dir, 'XLSX')
        
        self._stats['tiempo'] = time.time() - inicio
        
        self._reportar()
        
        if fts_path:
            self.construir_fts(fts_path)
    
    def _reportar(self):
        """Reporte final de carga."""
        stats = self.conn.execute("""
            SELECT 
                COUNT(DISTINCT fuente_id) as fuentes,
                COUNT(*) as registros,
                COUNT(DISTINCT clave_geo) as claves_unicas,
                COUNT(DISTINCT entidad) as entidades
            FROM registro
        """).fetchone()
        
        db_size = self.db_path.stat().st_size
        
        print(f"\n{'='*60}")
        print(f"CARGA SQLITE COMPLETADA (esquema optimizado v2)")
        print(f"{'='*60}")
        print(f"  Base de datos:   {self.db_path.name}")
        print(f"  Tamaño:          {db_size / 1024 / 1024:.1f} MB")
        print(f"  Fuentes:         {stats['fuentes']}")
        print(f"  Registros:       {stats['registros']:,}")
        print(f"  Claves geo únicas: {stats['claves_unicas']}")
        print(f"  Entidades:       {stats['entidades']}")
        print(f"  Duración:        {self._stats['tiempo']:.1f}s")
        print(f"\n  📍 {self.db_path.resolve()}")
        print(f"\n  💡 FTS5 se construye aparte con construir_fts()")
    
    def construir_fts(self, fts_path: Path):
        """Construye BD FTS5 aparte desde la BD principal.
        
        Crea un archivo SQLite separado con solo el índice FTS5,
        permitiendo que la BD principal sea más pequeña.
        
        Args:
            fts_path: Ruta donde crear la BD FTS5 (ej. data/datos_pdp_fts.db)
        """
        import json as _json
        
        print(f"\n🔍 Construyendo índice FTS5 en: {fts_path}")
        inicio = time.time()
        
        conn_fts = sqlite3.connect(str(fts_path))
        conn_fts.execute("PRAGMA synchronous=OFF")
        conn_fts.execute("PRAGMA cache_size=-4000000")
        conn_fts.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS registro_fts USING fts5(
                texto_busqueda, censo, modulo, entidad,
                content='', tokenize='unicode61'
            );
        """)
        
        batch_size = 5000
        total = 0
        last_id = 0
        
        while True:
            rows = self.conn.execute("""
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
            for r in rows:
                try:
                    datos = _json.loads(r['datos_json'])
                except (_json.JSONDecodeError, TypeError):
                    datos = {}
                censo = r['censo'] or ''
                modulo = r['modulo'] or ''
                texto = self._generar_texto_busqueda(datos, censo, modulo)
                batch.append((r['id'], texto, censo, modulo, r['entidad'] or ''))
            
            conn_fts.executemany("""
                INSERT INTO registro_fts(rowid, texto_busqueda, censo, modulo, entidad)
                VALUES (?, ?, ?, ?, ?)
            """, batch)
            conn_fts.commit()
            
            total += len(rows)
            last_id = rows[-1]['id']
            
            if total % 200000 == 0:
                print(f"  Progreso FTS5: {total:>8,}")
        
        conn_fts.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn_fts.close()
        
        size = fts_path.stat().st_size
        print(f"  ✅ FTS5: {size/1024/1024/1024:.1f} GB ({total:,} filas, {time.time()-inicio:.0f}s)")
    
    def cerrar(self):
        self.conn.close()

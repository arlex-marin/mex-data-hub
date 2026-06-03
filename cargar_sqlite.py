#!/usr/bin/env python3
"""
cargar_sqlite.py — Fase 0.3: Normalización y Carga en SQLite + FTS5.

Lee todos los datos parseados (DBF + CSV + XLSX) y los carga en una
base de datos SQLite unificada con índices y búsqueda FTS5.

Pipeline:
  1. Lee archivos JSONL de data/staging_dbf/ y data/staging_xlsx/
  2. Para cada archivo:
     a. Extrae metadatos (censo, año, módulo, nivel)
     b. Extrae claves geográficas (clave_geo, entidad, municipio)
     c. Inserta en tabla unificada 'registro'
  3. Crea catálogo de fuentes
  4. Construye índice FTS5 para búsqueda de texto completo
  5. Reporte final con estadísticas

Uso:
    python3 cargar_sqlite.py                              # carga completa
    python3 cargar_sqlite.py --db datos_pdp.db            # nombre personalizado

Salida:
    data/datos_pdp.db  — base de datos SQLite (~500 MB - 1 GB)
"""

import argparse
import time
from pathlib import Path

from ingesta.cargador import CargadorSQLite


def main():
    parser = argparse.ArgumentParser(
        description='Fase 0.3: Carga de datos en SQLite + FTS5'
    )
    parser.add_argument(
        '--db', default='datos_pdp.db',
        help='Nombre de la base de datos (default: datos_pdp.db)'
    )
    parser.add_argument(
        '--no-fts', action='store_true',
        help='No construir índice FTS5 (ahorra tiempo/espacio)'
    )
    args = parser.parse_args()
    
    base_dir = Path(__file__).resolve().parent
    dbf_dir = base_dir / 'data' / 'staging_dbf'
    xlsx_dir = base_dir / 'data' / 'staging_xlsx'
    db_path = base_dir / 'data' / args.db
    fts_path = None if args.no_fts else base_dir / 'data' / args.db.replace('.db', '_fts.db')
    
    print(f"{'='*60}")
    print(f"FASE 0.3 — Normalización y Carga en SQLite (esquema optimizado v2)")
    print(f"{'='*60}")
    print(f"  DBF/CSV staging:  {dbf_dir}")
    print(f"  XLSX staging:     {xlsx_dir}")
    print(f"  DB destino:       {db_path}")
    print(f"  FTS5 aparte:      {fts_path or 'No'}")
    print()
    
    if not dbf_dir.exists():
        print(f"❌ No existe: {dbf_dir}")
        return
    
    if not xlsx_dir.exists():
        print(f"❌ No existe: {xlsx_dir}")
        return
    
    cargador = CargadorSQLite(db_path)
    
    try:
        cargador.cargar_todo(dbf_dir, xlsx_dir, fts_path=fts_path)
    except KeyboardInterrupt:
        print("\n⚠️  Interrumpido por el usuario")
    finally:
        cargador.cerrar()


if __name__ == '__main__':
    main()

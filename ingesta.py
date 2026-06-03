#!/usr/bin/env python3
"""
ingesta.py — Orquestador de la Fase 0.1: Parseo de archivos DBF.

Pipeline:
  1. Encuentra todos los archivos .dbf.zip en microdatos_tabulados/
  2. Para cada ZIP:
     a. Extrae los DBF a un directorio temporal
     b. Parsea cada DBF con dbfread (raw mode, CP850→UTF-8)
     c. Guarda resultados como JSONL + metadatos en data/staging_dbf/
     d. Limpia temporales
  3. Procesamiento paralelo con ThreadPoolExecutor
  4. Reporte final de éxito/fallo

Uso:
    python3 ingesta.py                    # procesa todos los 245 ZIPs
    python3 ingesta.py --max 5            # procesa solo 5 archivos (prueba)
    python3 ingesta.py --workers 8        # 8 workers en paralelo (default: 4)

Salida:
    data/staging_dbf/*.jsonl              # registros decodificados
    data/staging_dbf/*.meta.json          # metadatos por tabla
    data/staging_dbf/resumen_ingesta.json # estadísticas consolidadas
"""

import argparse
import json
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List

from ingesta.descompresor import extraer_dbfs, extraer_csvs
from ingesta.dbf import parsear_dbf
from ingesta.csv_parser import parsear_csv


# ── Constantes ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
FUENTE_DIR = BASE_DIR / 'microdatos_tabulados'
SALIDA_DIR = BASE_DIR / 'data' / 'staging_dbf'
SALIDA_DIR.mkdir(parents=True, exist_ok=True)


# ── Procesamiento de un ZIP ────────────────────────────────────

def procesar_zip(zip_path: Path) -> Dict:
    """
    Procesa un archivo ZIP: extrae DBFs (o CSVs si no hay DBFs), 
    los parsea, guarda resultados.
    
    Args:
        zip_path: Ruta al archivo .dbf.zip
    
    Returns:
        Dict con estadísticas de procesamiento para este ZIP
    """
    nombre_zip = zip_path.name
    
    resultado = {
        'zip': nombre_zip,
        'ok': True,
        'tablas_parseadas': 0,
        'tablas_fallidas': 0,
        'total_registros': 0,
        'formato': 'desconocido',
        'tablas': [],
        'errores': []
    }
    
    with tempfile.TemporaryDirectory(prefix='ingesta_') as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Intentar DBF primero, luego CSV
        try:
            extraidos = extraer_dbfs(zip_path, tmpdir_path)
            if extraidos:
                resultado['formato'] = 'dbf'
                parser = parsear_dbf
            else:
                extraidos = extraer_csvs(zip_path, tmpdir_path)
                if extraidos:
                    resultado['formato'] = 'csv'
                    parser = parsear_csv
        except Exception as e:
            resultado['ok'] = False
            resultado['errores'].append(f'Error extrayendo ZIP: {e}')
            return resultado
        
        if not extraidos:
            resultado['errores'].append('No se encontraron archivos DBF ni CSV en el ZIP')
            return resultado
        
        for nombre, ruta in extraidos:
            try:
                parsed = parser(ruta)
                resultado['total_registros'] += parsed.get('total_registros', 0)
                
                if parsed.get('errores'):
                    resultado['errores'].extend(
                        f"{parsed['nombre_tabla']}: {e}" 
                        for e in parsed['errores'][:5]
                    )
                
                # Guardar datos
                prefijo = nombre_zip.replace('.dbf.zip', '').replace('.', '_')
                nombre_salida = f"{prefijo}__{parsed['nombre_tabla']}"
                
                archivo_jsonl = SALIDA_DIR / f"{nombre_salida}.jsonl"
                with open(archivo_jsonl, 'w', encoding='utf-8') as f:
                    for reg in parsed['registros']:
                        f.write(json.dumps(reg, ensure_ascii=False, default=str) + '\n')
                
                archivo_meta = SALIDA_DIR / f"{nombre_salida}.meta.json"
                meta = {k: v for k, v in parsed.items() if k != 'registros'}
                with open(archivo_meta, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2, default=str)
                
                resultado['tablas_parseadas'] += 1
                resultado['tablas'].append({
                    'nombre': parsed['nombre_tabla'],
                    'registros': parsed['total_registros'],
                    'campos': len(parsed.get('campos', []))
                })
                
            except Exception as e:
                resultado['tablas_fallidas'] += 1
                resultado['errores'].append(f"Error parseando {nombre}: {e}")
    
    return resultado


# ── Orquestador ────────────────────────────────────────────────

def ejecutar_ingesta(
    max_archivos: int = None,
    workers: int = 4
) -> List[Dict]:
    """
    Ejecuta la ingesta de todos los archivos DBF ZIP.
    
    Args:
        max_archivos: Limitar a N archivos (para pruebas), None = todos
        workers: Número de workers paralelos
    
    Returns:
        Lista de resultados por ZIP
    """
    zips = sorted(FUENTE_DIR.glob('*.dbf.zip'))
    
    if not zips:
        print("❌ No se encontraron archivos .dbf.zip en", FUENTE_DIR)
        return []
    
    if max_archivos:
        zips = zips[:max_archivos]
    
    print(f"📦 {len(zips)} archivos ZIP encontrados")
    print(f"⚙️  {workers} workers paralelos")
    print(f"📂 Salida: {SALIDA_DIR}")
    print()
    
    resultados = []
    inicio = time.time()
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {executor.submit(procesar_zip, zp): zp for zp in zips}
        
        for i, futuro in enumerate(as_completed(futuros), 1):
            zp = futuros[futuro]
            try:
                res = futuro.result()
                resultados.append(res)
                
                icono = '✅' if res['ok'] and not res['errores'] else '⚠️'
                formato = res.get('formato', 'dbf').upper()
                print(f"  [{i:3d}/{len(zips)}] {icono} {zp.name}"
                      f" → {res['tablas_parseadas']} tablas ({formato}), {res['total_registros']} registros"
                      f"{' ERR: ' + str(len(res['errores'])) if res['errores'] else ''}")
                
                if res['errores']:
                    for err in res['errores'][:2]:
                        print(f"         ⚠ {err}")
                    if len(res['errores']) > 2:
                        print(f"         ... y {len(res['errores']) - 2} errores más")
                        
            except Exception as e:
                resultados.append({
                    'zip': zp.name,
                    'ok': False,
                    'errores': [f'Error fatal: {e}']
                })
                print(f"  [{i:3d}/{len(zips)}] 💥 {zp.name} — {e}")
    
    duracion = time.time() - inicio
    
    # ── Reporte final ────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"INGESTA DBF COMPLETADA")
    print(f"{'='*60}")
    
    total_ok = sum(1 for r in resultados if r['ok'])
    total_tablas = sum(r['tablas_parseadas'] for r in resultados)
    total_registros = sum(r['total_registros'] for r in resultados)
    total_fallidos = sum(r['tablas_fallidas'] for r in resultados)
    total_errores = sum(len(r['errores']) for r in resultados)
    
    print(f"  ZIPs procesados:   {len(resultados)}")
    print(f"  ZIPs exitosos:     {total_ok}")
    print(f"  Tablas parseadas:  {total_tablas}")
    print(f"  Tablas fallidas:   {total_fallidos}")
    print(f"  Registros totales: {total_registros:,}")
    print(f"  Errores:           {total_errores}")
    print(f"  Duración:          {duracion:.1f}s")
    
    # Guardar resumen
    resumen = {
        'fase': '0.1 - Parseo DBF + CSV',
        'total_zips': len(resultados),
        'total_tablas_parseadas': total_tablas,
        'total_registros': total_registros,
        'total_errores': total_errores,
        'duracion_segundos': round(duracion, 1),
        'zips_procesados': [
            {
                'zip': r['zip'],
                'ok': r['ok'],
                'formato': r.get('formato', '?'),
                'tablas_parseadas': r.get('tablas_parseadas', 0),
                'registros': r.get('total_registros', 0),
                'errores': len(r.get('errores', []))
            }
            for r in resultados
        ]
    }
    
    with open(SALIDA_DIR / 'resumen_ingesta.json', 'w', encoding='utf-8') as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    
    print(f"\n📊 Resumen guardado en: {SALIDA_DIR / 'resumen_ingesta.json'}")
    
    return resultados


# ── CLI ────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Fase 0.1: Ingesta y parseo de archivos DBF ZIP de INEGI'
    )
    parser.add_argument(
        '--max', type=int, default=None,
        help='Procesar solo N archivos (para pruebas)'
    )
    parser.add_argument(
        '--workers', type=int, default=4,
        help='Workers paralelos (default: 4)'
    )
    
    args = parser.parse_args()
    ejecutar_ingesta(max_archivos=args.max, workers=args.workers)

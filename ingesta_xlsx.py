#!/usr/bin/env python3
"""
ingesta_xlsx.py — Fase 0.2: Parseo de archivos XLSX tabulados de INEGI.

Pipeline:
  1. Encuentra todos los archivos .xlsx en microdatos_tabulados/
  2. Parsea cada XLSX con openpyxl (data_only=True)
  3. Detecta automáticamente estructura de encabezados multi-fila
  4. Expande celdas combinadas con forward-fill
  5. Guarda resultados como JSONL + metadatos en data/staging_xlsx/
  6. Reporte final de éxito/fallo

Uso:
    python3 ingesta_xlsx.py                    # procesa todos los 156 XLSX
    python3 ingesta_xlsx.py --max 5            # solo 5 archivos (prueba)
    python3 ingesta_xlsx.py --workers 8        # 8 workers en paralelo (default: 4)

Salida:
    data/staging_xlsx/*.jsonl              # registros decodificados
    data/staging_xlsx/*.meta.json          # metadatos por archivo
    data/staging_xlsx/resumen_ingesta.json # estadísticas consolidadas
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List

from ingesta.xlsx import parsear_xlsx


# ── Constantes ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
FUENTE_DIR = BASE_DIR / 'microdatos_tabulados'
SALIDA_DIR = BASE_DIR / 'data' / 'staging_xlsx'
SALIDA_DIR.mkdir(parents=True, exist_ok=True)


# ── Procesamiento de un XLSX ───────────────────────────────────

def procesar_xlsx(filepath: Path) -> Dict:
    """
    Parsea un archivo XLSX y guarda resultados.
    
    Args:
        filepath: Ruta al archivo .xlsx
    
    Returns:
        Dict con estadísticas de procesamiento
    """
    nombre = filepath.name
    
    resultado = {
        'archivo': nombre,
        'ok': True,
        'hojas_parseadas': 0,
        'total_registros': 0,
        'errores': []
    }
    
    try:
        parsed = parsear_xlsx(filepath)
        
        resultado['total_registros'] = parsed['total_registros']
        resultado['hojas_parseadas'] = parsed['total_hojas']
        
        if parsed.get('errores'):
            resultado['errores'] = parsed['errores']
        
        if parsed['registros']:
            # Guardar datos como JSONL
            prefijo = parsed['nombre_archivo'].replace('.', '_')
            archivo_jsonl = SALIDA_DIR / f"{prefijo}.jsonl"
            
            with open(archivo_jsonl, 'w', encoding='utf-8') as f:
                for reg in parsed['registros']:
                    f.write(json.dumps(reg, ensure_ascii=False, default=str) + '\n')
            
            # Guardar metadatos
            archivo_meta = SALIDA_DIR / f"{prefijo}.meta.json"
            meta = {
                'archivo': parsed['nombre_archivo'],
                'censo': parsed['censo'],
                'año': parsed['año'],
                'modulo': parsed['modulo'],
                'total_registros': parsed['total_registros'],
                'total_hojas': parsed['total_hojas'],
                'campos': parsed['campos'],
                'errores': parsed['errores']
            }
            with open(archivo_meta, 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2, default=str)
            
            resultado['total_registros'] = parsed['total_registros']
        else:
            resultado['errores'].append(f'0 registros extraídos')
            
    except Exception as e:
        resultado['ok'] = False
        resultado['errores'].append(f'Error fatal: {e}')
    
    return resultado


# ── Orquestador ────────────────────────────────────────────────

def ejecutar_ingesta(
    max_archivos: int = None,
    workers: int = 4
) -> List[Dict]:
    """
    Ejecuta la ingesta de todos los archivos XLSX.
    
    Args:
        max_archivos: Limitar a N archivos (para pruebas)
        workers: Número de workers paralelos
    
    Returns:
        Lista de resultados por archivo
    """
    xlsx_files = sorted(FUENTE_DIR.glob('*.xlsx'))
    
    if not xlsx_files:
        print("❌ No se encontraron archivos .xlsx en", FUENTE_DIR)
        return []
    
    if max_archivos:
        xlsx_files = xlsx_files[:max_archivos]
    
    print(f"📊 {len(xlsx_files)} archivos XLSX encontrados")
    print(f"⚙️  {workers} workers paralelos")
    print(f"📂 Salida: {SALIDA_DIR}")
    print()
    
    resultados = []
    inicio = time.time()
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {executor.submit(procesar_xlsx, xp): xp for xp in xlsx_files}
        
        for i, futuro in enumerate(as_completed(futuros), 1):
            xp = futuros[futuro]
            try:
                res = futuro.result()
                resultados.append(res)
                
                icono = '✅' if res['ok'] and not res['errores'] else '⚠️'
                print(f"  [{i:3d}/{len(xlsx_files)}] {icono} {xp.name}"
                      f" → {res['hojas_parseadas']} hojas, {res['total_registros']} registros"
                      f"{' ERR: ' + str(len(res['errores'])) if res['errores'] else ''}")
                
                if res['errores']:
                    for err in res['errores'][:2]:
                        print(f"         ⚠ {err}")
                    if len(res['errores']) > 2:
                        print(f"         ... y {len(res['errores']) - 2} errores más")
                        
            except Exception as e:
                resultados.append({
                    'archivo': xp.name,
                    'ok': False,
                    'errores': [f'Error fatal: {e}']
                })
                print(f"  [{i:3d}/{len(xlsx_files)}] 💥 {xp.name} — {e}")
    
    duracion = time.time() - inicio
    
    # ── Reporte final ────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"INGESTA XLSX COMPLETADA")
    print(f"{'='*60}")
    
    total_ok = sum(1 for r in resultados if r['ok'])
    total_hojas = sum(r['hojas_parseadas'] for r in resultados)
    total_registros = sum(r['total_registros'] for r in resultados)
    total_errores = sum(len(r['errores']) for r in resultados)
    
    print(f"  XLSX procesados:   {len(resultados)}")
    print(f"  XLSX exitosos:     {total_ok}")
    print(f"  Hojas parseadas:   {total_hojas}")
    print(f"  Registros totales: {total_registros:,}")
    print(f"  Errores:           {total_errores}")
    print(f"  Duración:          {duracion:.1f}s")
    
    # Guardar resumen
    resumen = {
        'fase': '0.2 - Parseo XLSX',
        'total_xlsx': len(resultados),
        'total_hojas': total_hojas,
        'total_registros': total_registros,
        'total_errores': total_errores,
        'duracion_segundos': round(duracion, 1),
        'archivos_procesados': [
            {
                'archivo': r['archivo'],
                'ok': r['ok'],
                'hojas': r.get('hojas_parseadas', 0),
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
        description='Fase 0.2: Ingesta y parseo de archivos XLSX de INEGI'
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

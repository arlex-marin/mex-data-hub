"""
csv_parser.py — Parseador de archivos CSV legacy de INEGI.

Para archivos CSV encontrados dentro de ZIPs etiquetados como .dbf.zip
(variante atípica CNGMD 2017 residuos sólidos).
Decodifica CP850 → UTF-8.
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


def _adivinar_encodificacion(filepath: Path) -> str:
    """Prueba codificaciones comunes hasta encontrar una que funcione."""
    for enc in ['cp850', 'latin-1', 'utf-8-sig', 'utf-8']:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                f.read(100)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return 'cp850'


def parsear_csv(filepath: Path) -> Dict[str, Any]:
    """
    Parsea un archivo CSV a un diccionario con metadatos y registros.
    
    Args:
        filepath: Ruta al archivo .csv
    
    Returns:
        Dict con:
        - nombre_tabla: nombre del archivo sin extensión
        - campos: lista de nombres de columna
        - registros: lista de dicts con valores
        - total_registros: contador
        - errores: lista de mensajes de error
    """
    nombre_tabla = filepath.stem
    encoding = _adivinar_encodificacion(filepath)
    
    try:
        with open(filepath, 'r', encoding=encoding, newline='') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return {
                    'nombre_tabla': nombre_tabla,
                    'archivo': str(filepath),
                    'campos': [],
                    'registros': [],
                    'total_registros': 0,
                    'errores': ['CSV sin encabezado']
                }
            
            campos = [{'nombre': fn, 'tipo': 'C', 'tamano': 0, 'decimales': 0} 
                      for fn in reader.fieldnames]
            registros = []
            errores = []
            
            for i, row in enumerate(reader):
                cleaned = {}
                for k, v in row.items():
                    if v is None or v.strip() == '':
                        cleaned[k] = None
                    else:
                        try:
                            cleaned[k] = int(v)
                        except ValueError:
                            try:
                                cleaned[k] = float(v)
                            except ValueError:
                                cleaned[k] = v.strip()
                registros.append(cleaned)
                
    except Exception as e:
        return {
            'nombre_tabla': nombre_tabla,
            'archivo': str(filepath),
            'campos': [],
            'registros': [],
            'total_registros': 0,
            'errores': [f'Error parseando CSV: {e}']
        }
    
    return {
        'nombre_tabla': nombre_tabla,
        'archivo': str(filepath),
        'campos': campos,
        'registros': registros,
        'total_registros': len(registros),
        'errores': errores
    }

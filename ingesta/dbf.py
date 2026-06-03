"""
dbf.py — Parseador de archivos DBF legacy de INEGI.

Usa dbfread con raw=True para evitar fallos del parser automático
de campos (archivos con formato numérico inconsistente).
Decodifica CP850 → UTF-8 para caracteres españoles.
Maneja gracefulmente la ausencia de archivos memo (.FPT).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import dbfread


def _decodificar_valor(raw_val, tipo: str) -> Optional[Any]:
    """
    Decodifica un valor raw (bytes) según su tipo DBF.
    
    - C (Character): decodificar CP850 → UTF-8, quitar espacios extremos
    - N (Numeric): quitar espacios, convertir a int o float
    - D (Date), L (Logical), F (Float), M (Memo): decodificar como string
    
    Retorna None si el valor es vacío.
    """
    if raw_val is None:
        return None

    if isinstance(raw_val, bytes):
        decoded = raw_val.decode('cp850', errors='replace').strip()
    else:
        decoded = str(raw_val).strip()

    if not decoded:
        return None

    if tipo == 'N':
        try:
            if '.' in decoded:
                return float(decoded)
            return int(decoded)
        except (ValueError, TypeError):
            return decoded

    if tipo == 'L':
        decoded_lower = decoded.lower()
        if decoded_lower in ('t', 'y', '1', 'true', 'yes'):
            return True
        if decoded_lower in ('f', 'n', '0', 'false', 'no'):
            return False
        return decoded

    if tipo == 'D':
        return decoded  # fecha como string, normalizar después

    return decoded


def _decodificar_bytes(raw_val, encoding='cp850'):
    """Decodifica bytes preservando el valor si no es bytes."""
    if isinstance(raw_val, bytes):
        return raw_val.decode(encoding, errors='replace')
    return raw_val


def parsear_dbf(filepath: Path) -> Dict[str, Any]:
    """
    Parsea un archivo DBF a un diccionario con metadatos y registros.
    
    Args:
        filepath: Ruta al archivo .DBF
    
    Returns:
        Dict con:
        - nombre_tabla: nombre del archivo sin extensión
        - campos: lista de {nombre, tipo, tamaño, decimales}
        - registros: lista de dicts con valores decodificados
        - total_registros: contador
        - errores: lista de mensajes de error
    """
    nombre_tabla = filepath.stem
    
    try:
        table = dbfread.DBF(
            str(filepath),
            encoding='cp850',
            raw=True,
            ignore_missing_memofile=True,
            char_decode_errors='replace'
        )
    except Exception as e:
        return {
            'nombre_tabla': nombre_tabla,
            'archivo': str(filepath),
            'campos': [],
            'registros': [],
            'total_registros': 0,
            'errores': [f'No se pudo abrir el DBF: {e}']
        }
    
    campos = [
        {
            'nombre': f.name,
            'tipo': f.type,
            'tamano': f.length,
            'decimales': f.decimal_count
        }
        for f in table.fields
    ]
    
    registros = []
    errores = []
    
    for i, record in enumerate(table):
        fila = {}
        for campo_info in campos:
            nombre = campo_info['nombre']
            raw_val = record.get(nombre)
            
            try:
                fila[nombre] = _decodificar_valor(raw_val, campo_info['tipo'])
            except Exception as e:
                fila[nombre] = _decodificar_bytes(raw_val)
                errores.append(f'Fila {i}, campo {nombre}: {e}')
        
        registros.append(fila)
    
    return {
        'nombre_tabla': nombre_tabla,
        'archivo': str(filepath),
        'campos': campos,
        'registros': registros,
        'total_registros': len(registros),
        'errores': errores
    }


def parsear_y_guardar(filepath: Path, salida_dir: Path) -> Dict[str, Any]:
    """
    Parsea un DBF y guarda resultado como JSON lines en salida_dir.
    
    Retorna el mismo diccionario que parsear_dbf, con la ruta de salida añadida.
    """
    resultado = parsear_dbf(filepath)
    
    nombre_salida = f"{resultado['nombre_tabla']}.jsonl"
    ruta_salida = salida_dir / nombre_salida
    
    with open(ruta_salida, 'w', encoding='utf-8') as f:
        for registro in resultado['registros']:
            f.write(json.dumps(registro, ensure_ascii=False) + '\n')
    
    # Guardar metadatos aparte
    meta = {
        'nombre_tabla': resultado['nombre_tabla'],
        'archivo': resultado['archivo'],
        'campos': resultado['campos'],
        'total_registros': resultado['total_registros'],
        'errores': resultado['errores']
    }
    
    ruta_meta = salida_dir / f"{resultado['nombre_tabla']}.meta.json"
    with open(ruta_meta, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, default=str)
    
    resultado['ruta_salida'] = str(ruta_salida)
    return resultado

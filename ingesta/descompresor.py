"""
descompresor.py — Extrae archivos de datos de archivos ZIP de microdatos INEGI.

Maneja múltiples variantes estructurales:
  DBF:
    1. 2011:  Base de datos/*.DBF, Catálogos/*.DBF
    2. 2013:  {modulo}/Bases_de_datos/*.dbf, {modulo}/Catalogos/*.dbf
    3. 2017+: Bases_Datos/*.DBF, Catalogos/*.DBF
  CSV (atípico, CNGMD 2017 residuos sólidos):
    4. 2017:  {modulo}/Bases_Datos/*.csv, {modulo}/Catalogos/*.csv
"""

import os
import zipfile
from pathlib import Path
from typing import List, Tuple


def _categorizar(ruta: str) -> str:
    """Clasifica un archivo según su ubicación en el ZIP."""
    upper = ruta.upper()
    if 'CATALOG' in upper or 'CATÁLOG' in upper:
        return 'catalogo'
    elif 'BASE' in upper:
        return 'base'
    return 'desconocida'


def extraer_dbfs(zip_path: Path, destino_dir: Path) -> List[Tuple[str, Path]]:
    """
    Extrae todos los archivos DBF de un ZIP a un directorio destino.
    
    Args:
        zip_path: Ruta al archivo .dbf.zip
        destino_dir: Directorio donde extraer los archivos
    
    Returns:
        Lista de (nombre_salida, ruta_temp) para cada DBF extraído
    """
    extraidos = []
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for miembro in zf.namelist():
            if not miembro.upper().endswith('.DBF'):
                continue
            
            nombre_archivo = os.path.basename(miembro)
            nombre_salida = f"{_categorizar(miembro)}_{nombre_archivo}"
            zf.extract(miembro, destino_dir)
            ruta_extraida = destino_dir / miembro
            
            if ruta_extraida.exists():
                extraidos.append((nombre_salida, ruta_extraida))
    
    return extraidos


def extraer_csvs(zip_path: Path, destino_dir: Path) -> List[Tuple[str, Path]]:
    """
    Extrae archivos CSV de un ZIP (variante atípica CNGMD 2017).
    
    Args:
        zip_path: Ruta al archivo .dbf.zip
        destino_dir: Directorio donde extraer los archivos
    
    Returns:
        Lista de (nombre_salida, ruta_temp) para cada CSV extraído
    """
    extraidos = []
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for miembro in zf.namelist():
            if not miembro.upper().endswith('.CSV'):
                continue
            
            nombre_archivo = os.path.basename(miembro)
            nombre_salida = f"{_categorizar(miembro)}_{nombre_archivo}"
            zf.extract(miembro, destino_dir)
            ruta_extraida = destino_dir / miembro
            
            if ruta_extraida.exists():
                extraidos.append((nombre_salida, ruta_extraida))
    
    return extraidos


def listar_dbfs_en_zip(zip_path: Path) -> List[str]:
    """
    Lista los nombres de archivos DBF dentro de un ZIP sin extraerlos.
    Útil para conteo y reporte previo.
    """
    with zipfile.ZipFile(zip_path, 'r') as zf:
        return [m for m in zf.namelist() if m.upper().endswith('.DBF')]


def listar_csvs_en_zip(zip_path: Path) -> List[str]:
    """
    Lista los nombres de archivos CSV dentro de un ZIP sin extraerlos.
    """
    with zipfile.ZipFile(zip_path, 'r') as zf:
        return [m for m in zf.namelist() if m.upper().endswith('.CSV')]

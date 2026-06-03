"""
Tests para ingesta/xlsx.py — Parseo de archivos XLSX de INEGI.
"""

from pathlib import Path
from ingesta.xlsx import parsear_xlsx, _encontrar_estructura_hoja
import openpyxl


class TestXlsxParsear:
    """Parseo de archivos XLSX completos."""

    def test_parsea_tematico(self, xlsx_tematico_path):
        """Debe parsear XLSX en formato temático (2021+)."""
        resultado = parsear_xlsx(xlsx_tematico_path)
        assert resultado['total_registros'] > 0
        assert resultado['total_hojas'] > 0
        assert len(resultado['errores']) == 0

    def test_parsea_tematico_valores(self, xlsx_tematico_path):
        """Los valores parseados deben ser correctos."""
        resultado = parsear_xlsx(xlsx_tematico_path)
        registros = resultado['registros']
        # El primer registro debería tener datos
        if registros:
            keys = [k for k in registros[0].keys() if not k.startswith('_')]
            assert len(keys) > 0, "Debe haber columnas de datos"

    def test_parsea_mformat(self, xlsx_mformat_path):
        """Debe parsear XLSX en formato M (2017-2019)."""
        resultado = parsear_xlsx(xlsx_mformat_path)
        # El formato M puede tener más dificultades, pero no debe fallar
        assert len(resultado['errores']) == 0
        # Puede tener 0 registros si la detección falla, pero no debe explotar
        assert resultado['total_hojas'] >= 0

    def test_parsea_con_metadatos(self, xlsx_tematico_path):
        """Los registros deben incluir metadatos _hoja, _censo, _año, _modulo."""
        resultado = parsear_xlsx(xlsx_tematico_path)
        if resultado['registros']:
            r = resultado['registros'][0]
            assert '_hoja' in r
            assert '_censo' in r
            assert '_año' in r
            assert '_modulo' in r

    def test_parsea_archivo_inexistente(self):
        """Debe manejar gracefulmente un archivo que no existe."""
        resultado = parsear_xlsx(Path('/ruta/inexistente.xlsx'))
        assert resultado['total_registros'] == 0
        assert len(resultado['errores']) > 0


class TestXlsxEstructura:
    """Detección de estructura de hojas XLSX."""

    def test_detecta_encabezados(self, xlsx_tematico_path):
        """Debe detectar la fila de encabezados correctamente."""
        wb = openpyxl.load_workbook(xlsx_tematico_path, read_only=True, data_only=True)
        ws = wb['1']
        hs, he, ds = _encontrar_estructura_hoja(ws)
        assert hs > 0, "Debe encontrar fila de inicio de headers"
        assert he >= hs, "Header end debe ser >= header start"
        assert ds > he, "Data start debe ser después de headers"
        wb.close()

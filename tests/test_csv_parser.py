"""
Tests para ingesta/csv_parser.py — Parseo de archivos CSV legacy.
"""

from ingesta.csv_parser import parsear_csv


class TestParsearCsv:
    """Parseo de archivos CSV (variante CNGMD 2017 RSU)."""

    def test_parsea_csv_basico(self, csv_sample_path):
        """Debe parsear un CSV simple con encoding CP850."""
        resultado = parsear_csv(csv_sample_path)
        assert resultado['total_registros'] == 3
        assert len(resultado['campos']) == 4
        nombres = [c['nombre'] for c in resultado['campos']]
        assert 'folio' in nombres
        assert 'entidad' in nombres
        assert len(resultado['errores']) == 0

    def test_parsea_csv_valores(self, csv_sample_path):
        """Los valores deben decodificarse correctamente."""
        resultado = parsear_csv(csv_sample_path)
        assert resultado['registros'][0]['folio'] == 1001
        assert resultado['registros'][0]['entidad'] == 'Jalisco'
        assert resultado['registros'][0]['valor'] == 95.2

    def test_parsea_csv_vacio(self, tmp_path):
        """CSV vacío debe retornar 0 registros."""
        path = tmp_path / 'vacio.csv'
        with open(path, 'w', encoding='utf-8') as f:
            f.write('col1,col2\n')
        resultado = parsear_csv(path)
        assert resultado['total_registros'] == 0

    def test_parsea_csv_con_nulos(self, tmp_path):
        """Campos vacíos deben convertirse a None."""
        path = tmp_path / 'nulos.csv'
        with open(path, 'w', encoding='cp850') as f:
            f.write('a,b,c\n1,,3\n')
        resultado = parsear_csv(path)
        assert resultado['total_registros'] == 1
        assert resultado['registros'][0]['a'] == 1
        assert resultado['registros'][0]['b'] is None
        assert resultado['registros'][0]['c'] == 3

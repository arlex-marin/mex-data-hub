"""
Tests para ingesta/dbf.py — Parseo de archivos DBF legacy.
"""

from ingesta.dbf import parsear_dbf, _decodificar_valor


class TestDecodificarValor:
    """Decodificación de valores DBF raw → Python."""

    def test_decodifica_caracter(self):
        """Campo C (character) debe decodificarse de CP850 a UTF-8."""
        val = _decodificar_valor(b'Hola', 'C')
        assert val == 'Hola'

    def test_decodifica_caracter_con_acento(self):
        """Caracteres CP850 como 'é' deben decodificarse correctamente."""
        val = _decodificar_valor('México'.encode('cp850'), 'C')
        assert val == 'México'

    def test_decodifica_numerico_entero(self):
        """Campo N (numeric) sin decimales debe convertirse a int."""
        val = _decodificar_valor(b'  123', 'N')
        assert val == 123
        assert isinstance(val, int)

    def test_decodifica_numerico_flotante(self):
        """Campo N con decimales debe convertirse a float."""
        val = _decodificar_valor(b'  1500.50', 'N')
        assert val == 1500.5
        assert isinstance(val, float)

    def test_decodifica_none(self):
        """Valor None debe retornar None."""
        val = _decodificar_valor(None, 'C')
        assert val is None

    def test_decodifica_vacio(self):
        """Valor vacío debe retornar None."""
        val = _decodificar_valor(b'   ', 'C')
        assert val is None

    def test_decodifica_logico_true(self):
        """Campo L (logical) con 'T' debe ser True."""
        val = _decodificar_valor(b'T', 'L')
        assert val is True

    def test_decodifica_logico_false(self):
        """Campo L con 'F' debe ser False."""
        val = _decodificar_valor(b'F', 'L')
        assert val is False


class TestParsearDbf:
    """Parseo completo de archivos DBF."""

    def test_parsea_dbf_basico(self, dbf_sample_path):
        """Debe parsear un DBF simple y retornar registros."""
        resultado = parsear_dbf(dbf_sample_path)
        assert resultado['nombre_tabla'] == 'test_sample'
        assert resultado['total_registros'] == 3
        assert len(resultado['campos']) == 3
        # Los nombres de campo en DBF vienen con padding a 11 caracteres
        nombres = [c['nombre'].strip() for c in resultado['campos']]
        assert 'CODIGO' in nombres
        assert len(resultado['registros']) == 3
        # raw mode devuelve bytes; verificamos contenido decodificado
        reg = resultado['registros'][0]
        valores = {k.strip(): v for k, v in reg.items()}
        assert str(valores.get('CODIGO', '')).strip() == '001'
        assert len(resultado['errores']) == 0

    def test_parsea_dbf_con_cp850(self, dbf_sample_cp850_path):
        """Debe decodificar correctamente caracteres CP850 (acentos, eñes)."""
        resultado = parsear_dbf(dbf_sample_cp850_path)
        valores = []
        for r in resultado['registros']:
            v = {k.strip(): v for k, v in r.items()}
            valores.append(v)
        nombres = [str(v.get('NOMBRE', '')).strip() for v in valores]
        assert 'México' in nombres, f"CP850 'México' no decodificó. Nombres: {nombres}"
        assert 'Michoacán' in nombres
        assert len(resultado['errores']) == 0

    def test_parsea_dbf_y_guarda(self, dbf_sample_path, tmp_path):
        """parsear_y_guardar debe crear archivos JSONL y meta."""
        from ingesta.dbf import parsear_y_guardar
        resultado = parsear_y_guardar(dbf_sample_path, tmp_path)
        assert resultado['total_registros'] == 3
        jsonl_files = list(tmp_path.glob('*.jsonl'))
        meta_files = list(tmp_path.glob('*.meta.json'))
        assert len(jsonl_files) >= 1
        assert len(meta_files) >= 1

    def test_parsea_archivo_inexistente(self):
        """Debe manejar gracefulmente un archivo que no existe."""
        from pathlib import Path
        resultado = parsear_dbf(Path('/ruta/inexistente.dbf'))
        assert resultado['total_registros'] == 0
        assert len(resultado['errores']) > 0

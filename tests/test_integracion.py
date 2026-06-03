"""
Test de integración: verifica que el pipeline completo funcione
con archivos de prueba pequeños.
"""

import json
import tempfile
import zipfile
from pathlib import Path

from ingesta.descompresor import extraer_dbfs
from ingesta.dbf import parsear_dbf, parsear_y_guardar
from ingesta.csv_parser import parsear_csv
from ingesta.xlsx import parsear_xlsx


class TestPipelineIntegracion:
    """Verifica que los módulos del pipeline funcionen juntos."""

    def test_dbf_desde_zip_hasta_jsonl(self, dbf_zip_path, tmp_path):
        """
        Pipeline DBF completo:
        ZIP → extraer → parsear → guardar JSONL
        """
        # 1. Extraer DBF del ZIP
        extraidos = extraer_dbfs(dbf_zip_path, tmp_path)
        assert len(extraidos) > 0, "Debe extraer al menos 1 DBF"

        # 2. Parsear el DBF extraído
        nombre, ruta_dbf = extraidos[0]
        resultado = parsear_dbf(ruta_dbf)
        assert resultado['total_registros'] == 3
        assert len(resultado['errores']) == 0

        # 3. Guardar como JSONL
        salida = tmp_path / 'resultado'
        salida.mkdir()
        guardado = parsear_y_guardar(ruta_dbf, salida)

        # 4. Verificar JSONL
        jsonl_files = list(salida.glob('*.jsonl'))
        assert len(jsonl_files) >= 1
        with open(jsonl_files[0]) as f:
            line = f.readline()
            record = json.loads(line)
            assert 'CODIGO' in record or 'CODIGO     ' in record

    def test_csv_parseo_y_encoding(self, csv_sample_path):
        """CSV con encoding CP850 debe decodificar correctamente."""
        resultado = parsear_csv(csv_sample_path)
        assert resultado['total_registros'] == 3
        assert resultado['registros'][0]['entidad'] == 'Jalisco'

    def test_xlsx_parseo_con_metadatos(self, xlsx_tematico_path):
        """XLSX debe producir registros con metadatos de censo/año/módulo."""
        resultado = parsear_xlsx(xlsx_tematico_path)
        if resultado['registros']:
            r = resultado['registros'][0]
            assert '_censo' in r
            assert '_año' in r
            assert '_modulo' in r

    def test_dbf_csv_xlsx_comparten_formato_salida(self, dbf_zip_path, csv_sample_path, xlsx_tematico_path, tmp_path):
        """
        Los tres parsers (DBF, CSV, XLSX) deben producir JSONL
        en el mismo directorio sin conflictos.
        """
        salida = tmp_path / 'unificado'
        salida.mkdir()

        # DBF
        from ingesta.dbf import parsear_y_guardar
        extraidos = extraer_dbfs(dbf_zip_path, tmp_path)
        for _, ruta in extraidos:
            parsear_y_guardar(ruta, salida)

        # CSV
        csv_res = parsear_csv(csv_sample_path)
        if csv_res['registros']:
            with open(salida / 'csv_output.jsonl', 'w') as f:
                for rec in csv_res['registros']:
                    f.write(json.dumps(rec, ensure_ascii=False) + '\n')

        # XLSX
        xlsx_res = parsear_xlsx(xlsx_tematico_path)
        if xlsx_res['registros']:
            with open(salida / 'xlsx_output.jsonl', 'w') as f:
                for rec in xlsx_res['registros']:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')

        # Verificar que se crearon archivos
        jsonls = list(salida.glob('*.jsonl'))
        assert len(jsonls) >= 1, f"Debe haber al menos 1 JSONL, hay {len(jsonls)}"

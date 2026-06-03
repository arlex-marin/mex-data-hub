"""
Tests para ingesta/descompresor.py — Extracción de DBF/CSV desde ZIPs.
"""

import tempfile
from pathlib import Path

from ingesta.descompresor import extraer_dbfs, extraer_csvs


class TestExtraerDbfs:
    """Extracción de DBF desde ZIPs con diferentes estructuras."""

    def test_extrae_dbfs_formato_2017(self, dbf_zip_path):
        """Debe extraer DBFs de ZIP con estructura Bases_Datos/ (formato 2017+)."""
        with tempfile.TemporaryDirectory() as tmp:
            extraidos = extraer_dbfs(dbf_zip_path, Path(tmp))
            assert len(extraidos) > 0, "Debería encontrar al menos 1 DBF"
            nombre, ruta = extraidos[0]
            assert 'catalogo' in nombre or 'base' in nombre
            assert ruta.exists()
            assert ruta.suffix.upper() == '.DBF' or ruta.suffix.lower() == '.dbf'

    def test_extrae_dbfs_formato_2011(self, dbf_zip_2011_path):
        """Debe extraer DBFs de ZIP con estructura 'Base de datos/' (formato 2011)."""
        with tempfile.TemporaryDirectory() as tmp:
            extraidos = extraer_dbfs(dbf_zip_2011_path, Path(tmp))
            assert len(extraidos) > 0

    def test_extrae_dbfs_formato_2013(self, dbf_zip_2013_path):
        """Debe extraer DBFs de ZIP con estructura 'Bases_de_datos/' (formato 2013)."""
        with tempfile.TemporaryDirectory() as tmp:
            extraidos = extraer_dbfs(dbf_zip_2013_path, Path(tmp))
            assert len(extraidos) > 0


class TestExtraerCsvs:
    """Extracción de CSV desde ZIPs (variante CNGMD 2017 RSU)."""

    def test_extrae_csvs_de_zip_sin_dbf(self, csv_sample_path):
        """Debe extraer CSVs de un ZIP que no contiene DBFs."""
        zip_path = Path(csv_sample_path.parent) / 'test_csv_only.zip'
        import zipfile
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(csv_sample_path, 'Bases_Datos/datos.csv')

        with tempfile.TemporaryDirectory() as tmp:
            extraidos = extraer_csvs(zip_path, Path(tmp))
            assert len(extraidos) > 0
            assert any('csv' in n.lower() or '.csv' in n for n, _ in extraidos)

        zip_path.unlink()  # cleanup

    def test_extraer_dbfs_zip_sin_dbf_retorna_vacio(self, csv_sample_path):
        """Extraer DBFs de un ZIP que solo tiene CSVs debe retornar vacío."""
        zip_path = Path(csv_sample_path.parent) / 'test_csv_only2.zip'
        import zipfile
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(csv_sample_path, 'Bases_Datos/datos.csv')

        with tempfile.TemporaryDirectory() as tmp:
            extraidos = extraer_dbfs(zip_path, Path(tmp))
            assert len(extraidos) == 0

        zip_path.unlink()

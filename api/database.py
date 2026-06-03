"""
database.py — Conexión a las bases de datos SQLite para la API.

Maneja conexiones lazy a datos_pdp.db y datos_pdp_fts.db.
"""

import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent.parent / 'data'
DB_PATH = DB_DIR / 'datos_pdp.db'
DB_FTS_PATH = DB_DIR / 'datos_pdp_fts.db'


class Database:
    """Mantiene conexiones a las bases de datos principal y FTS5."""

    def __init__(self):
        self._conn: sqlite3.Connection | None = None
        self._conn_fts: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            if not DB_PATH.exists():
                raise FileNotFoundError(
                    f"BD principal no encontrada: {DB_PATH}. "
                    "Ejecuta primero el pipeline de ingesta."
                )
            self._conn = sqlite3.connect(str(DB_PATH))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA cache_size=-8000000")
        return self._conn

    @property
    def conn_fts(self) -> sqlite3.Connection | None:
        if not DB_FTS_PATH.exists():
            return None
        if self._conn_fts is None:
            self._conn_fts = sqlite3.connect(str(DB_FTS_PATH))
            self._conn_fts.row_factory = sqlite3.Row
        return self._conn_fts

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
        if self._conn_fts:
            self._conn_fts.close()
            self._conn_fts = None


# Singleton global
db = Database()

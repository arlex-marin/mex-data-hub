#!/usr/bin/env bash
# ============================================================
# setup.sh — Instalación automatizada del proyecto PDP
# ============================================================
# Uso:
#   ./setup.sh               # setup básico (dependencias + tests)
#   ./setup.sh --full         # setup completo (incluye ingesta)
#   ./setup.sh --help         # esta ayuda
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  PDP — Plataforma de Datos Públicos Mexicanos       ║"
echo "║  Setup automatizado                                 ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Requisitos ──────────────────────────────────────────────
echo "📋 Verificando requisitos..."

PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1 || echo "0")
echo "   Python: $(python3 --version 2>&1) (mínimo 3.11)"

# Verificar versión de Python
if (( $(echo "$PYTHON_VERSION < 3.11" | bc -l) )); then
    echo "   ❌ Se requiere Python 3.11+"
    exit 1
fi

# Verificar sqlite3
if python3 -c "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(content)')" 2>/dev/null; then
    echo "   ✅ SQLite + FTS5 disponible"
else
    echo "   ❌ SQLite sin soporte FTS5"
    echo "   → Instalar: pip install pysqlite3-binary  (o compilar SQLite con FTS5)"
    exit 1
fi

# ── Dependencias Python ─────────────────────────────────────
echo ""
echo "📦 Instalando dependencias Python..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt 2>&1 | tail -1
echo "   ✅ Dependencias instaladas"

# ── Tests ───────────────────────────────────────────────────
echo ""
echo "🧪 Ejecutando tests unitarios..."
python3 -m pytest tests/ -v --tb=short 2>&1
echo ""
echo "   ✅ Tests completados"

# ── Full setup: ingesta ─────────────────────────────────────
if [[ "${1:-}" == "--full" ]]; then
    echo ""
    echo "📥 Ejecutando ingesta completa..."
    echo "   (Requiere archivos INEGI en microdatos_tabulados/)"
    echo ""
    
    if [ -d "microdatos_tabulados" ] && [ "$(ls -A microdatos_tabulados/ 2>/dev/null)" ]; then
        echo "   Paso 1/3: Parseo DBF..."
        python3 ingesta.py && echo "   ✅ DBF parseados"
        
        echo "   Paso 2/3: Parseo XLSX..."
        python3 ingesta_xlsx.py && echo "   ✅ XLSX parseados"
        
        echo "   Paso 3/3: Carga SQLite..."
        python3 cargar_sqlite.py --no-fts && echo "   ✅ BD principal creada"
        
        echo "   FTS5 aparte..."
        python3 cargar_sqlite.py && echo "   ✅ FTS5 creado"
        
        echo ""
        echo "   ✅ Ingesta completa"
        ls -lh data/datos_pdp.db data/datos_pdp_fts.db 2>/dev/null
    else
        echo "   ⚠️  Directorio microdatos_tabulados/ vacío o inexistente"
        echo "   → Descarga los archivos de INEGI primero"
    fi
fi

# ── Resumen ─────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ Setup completado                                 ║"
echo "║                                                      ║"
echo "║  Próximos pasos:                                     ║"
echo "║  • ./setup.sh --full  → ingesta completa             ║"
echo "║  • python3 cargar_sqlite.py                          ║"
echo "║  • Consultar: sqlite3 data/datos_pdp.db              ║"
echo "╚══════════════════════════════════════════════════════╝"

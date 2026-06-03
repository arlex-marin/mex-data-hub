# Plataforma de Datos Públicos Mexicanos

[![Tests](https://github.com/arlex-marin/mex-data-hub/actions/workflows/tests.yml/badge.svg)](https://github.com/arlex-marin/mex-data-hub/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)]()
[![SQLite + FTS5](https://img.shields.io/badge/SQLite-FTS5-green)]()
[![License](https://img.shields.io/badge/License-CC--BY--4.0-lightgrey)]()
[![Roadmap](https://img.shields.io/badge/Roadmap-ver-green)](ROADMAP.md)

Pipeline de ingesta, parseo y API REST para datos unificados

## Requisitos

- Python 3.11+
- SQLite con soporte FTS5
- ~5 GB de espacio en disco

## Instalación

```bash
pip install -r requirements.txt
```

## Pipeline

```bash
# Paso 1: Parseo DBF/CSV (~2 min, 245 ZIPs)
python3 ingesta.py

# Paso 2: Parseo XLSX (~8 min, 156 archivos)
python3 ingesta_xlsx.py

# Paso 3: Carga en SQLite (~10 min)
python3 cargar_sqlite.py

# Opcional: optimizar BD existente
python3 optimizar_bd.py
```

## Estructura

```
code-pdp/
├── ingesta.py              # Orquestador de parseo DBF/CSV
├── ingesta_xlsx.py         # Orquestador de parseo XLSX
├── cargar_sqlite.py        # Carga unificada a SQLite + FTS5
├── optimizar_bd.py         # Migración a esquema optimizado v2
├── estandarizar_nombres.py # Normalización de nombres de archivo INEGI
├── ingesta/
│   ├── descompresor.py     # Extracción de DBF/CSV desde ZIPs
│   ├── dbf.py              # Parseo DBF (dbfread, CP850→UTF-8)
│   ├── csv_parser.py       # Parseo CSV (variante atípica CNGMD 2017)
│   └── xlsx.py             # Parseo XLSX (M-format + temático)
│   └── cargador.py         # Carga en SQLite (esquema v2, FTS5 aparte)
├── tests/                  # Tests unitarios e integración (31 tests)
│   ├── conftest.py         # Fixtures generados al vuelo
│   ├── test_dbf.py         # DBF parser (decodificación, CP850)
│   ├── test_csv_parser.py  # CSV parser
│   ├── test_xlsx.py        # XLSX parser (temático, M-format)
│   ├── test_descompresor.py # Extracción ZIP
│   └── test_integracion.py # Pipeline integrado
├── microdatos_tabulados/   # Archivos fuente INEGI (descarga externa)
├── data/                   # Datos generados (staging + BD)
│   ├── staging_dbf/        # JSONL intermedios DBF
│   ├── staging_xlsx/       # JSONL intermedios XLSX
│   ├── datos_pdp.db        # BD principal (~3.4 GB, esquema v2)
│   └── datos_pdp_fts.db    # Índice FTS5 aparte (~0.9 GB)
├── requirements.txt
└── setup.sh (en raíz del proyecto)
```

## API REST

La API FastAPI expone los datos vía HTTP con documentación OpenAPI interactiva.

```bash
# Iniciar servidor
python3 -m api.main

# Servidor en http://localhost:8000
# Documentación: http://localhost:8000/docs
```

| Endpoint | Descripción |
|:---------|:------------|
| `GET /` | Raíz con enlaces a documentación |
| `GET /api/health` | Health check de componentes |
| `GET /api/info` | Estadísticas generales del sistema |
| `GET /api/tablas` | Catálogo de fuentes con filtros |
| `GET /api/consulta` | Datos con filtros combinados |
| `GET /api/buscar?q=...` | Búsqueda FTS5 de texto completo |
| `GET /api/exportar/{csv\|json}` | Exportación de datos filtrados |

Ejemplos:

```bash
# Listar fuentes
curl "http://localhost:8000/api/tablas?censo=CNGMD&por_pagina=5"

# Buscar "agua potable"
curl "http://localhost:8000/api/buscar?q=agua&por_pagina=3"

# Consultar datos de Jalisco
curl "http://localhost:8000/api/consulta?entidad=Jalisco&por_pagina=2"

# Exportar a JSON
curl "http://localhost:8000/api/exportar/json?censo=CNGF&max_registros=10"
```

## Tests

```bash
python3 -m pytest tests/ -v    # 31 tests
```

## Esquema de BD (v2)

```
datos_pdp.db:
  catalogo  — metadatos de fuentes (censo, año, módulo, tipo_fuente)
  registro  — datos con JSON compacto, clave_geo, entidad, municipio
  vista_periodo    — resuelve año_publicación → periodo del censo
  vista_consulta   — consulta unificada con todos los metadatos

datos_pdp_fts.db:
  registro_fts — FTS5 autocontenido (texto_busqueda, censo, modulo, entidad)
```

## Consultas de ejemplo

```sql
-- ¿Cuántas fuentes por censo?
SELECT censo, COUNT(*) FROM catalogo GROUP BY censo;

-- Búsqueda FTS5
SELECT rowid, texto_busqueda FROM registro_fts 
WHERE texto_busqueda MATCH 'agua potable' LIMIT 10;

-- Registros de Jalisco
SELECT entidad, municipio FROM registro WHERE entidad LIKE '%Jalisco%';
```

## Licencia

Código: proyecto de código abierto.
Datos: © INEGI — Censos Nacionales de Gobierno. Sujeto a términos INEGI.

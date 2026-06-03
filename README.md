# Plataforma de Datos Públicos Mexicanos

[![Tests](https://github.com/arlex-marin/mex-data-hub/actions/workflows/tests.yml/badge.svg)](https://github.com/arlex-marin/mex-data-hub/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)]()
[![SQLite](https://img.shields.io/badge/SQLite-FTS5-003b57)]()
[![License](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey)]()

**API REST + base de datos SQLite unificada** que integra **7.4 millones de registros** de los Censos Nacionales de Gobierno del INEGI (México) para los tres niveles de gobierno: **federal (CNGF)**, **estatal (CNGE)** y **municipal (CNGMD)**, abarcando el período **2011–2025**.

Actualmente en fase activa de desarrollo. [Ver roadmap](ROADMAP.md).

---

## Características

- **7.4M registros** de 3,655 fuentes distintas
- **3 niveles de gobierno**: federal, estatal, municipal (CNGF, CNGE, CNGMD)
- **15 años de cobertura**: 2011 a 2025
- **3,028 claves geográficas** únicas (estados y municipios)
- **Búsqueda de texto completo** con índice FTS5
- **API REST** con documentación OpenAPI (Swagger)
- **Datos autocontenidos** en SQLite, sin dependencia de servicios externos

## Tabla de contenido

- [Requisitos](#requisitos)
- [Instalación rápida](#instalación-rápida)
- [Pipeline de ingesta](#pipeline-de-ingesta)
- [API REST](#api-rest)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Datos incluidos](#datos-incluidos)
- [Tests](#tests)
- [Roadmap](#roadmap)
- [Licencia y atribución](#licencia-y-atribución)

---

## Requisitos

- **Python** 3.11 o superior
- **SQLite** con soporte para FTS5 (incluido en Python por defecto)
- **~5 GB** de espacio en disco (para la base de datos)

## Instalación rápida

```bash
# Clonar el repositorio
git clone https://github.com/arlex-marin/mex-data-hub.git
cd mex-data-hub

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar tests
python3 -m pytest tests/
```

---

## Pipeline de ingesta

Para reconstruir la base de datos desde los archivos fuente de INEGI:

```bash
# Requiere los archivos .dbf.zip y .xlsx de INEGI
# en el directorio microdatos_tabulados/

python3 ingesta.py            # Parseo DBF (245 archivos ZIP)
python3 ingesta_xlsx.py       # Parseo XLSX (156 archivos)
python3 cargar_sqlite.py      # Carga en SQLite

# Opcional: construir índice FTS5
python3 cargar_sqlite.py
```

Para regenerar la base de datos desde los archivos JSONL intermedios:

```bash
python3 cargar_sqlite.py
```

---

## API REST

El servidor FastAPI expone los datos a través de endpoints con documentación interactiva.

```bash
# Iniciar servidor
python3 -m api.main

# Abrir en el navegador:
# http://localhost:8000/docs
```

### Endpoints

| Endpoint | Método | Descripción |
|:---------|:-------|:------------|
| `GET /` | — | Raíz con enlaces a documentación |
| `GET /api/health` | — | Estado de los componentes del sistema |
| `GET /api/info` | — | Estadísticas generales de la base de datos |
| `GET /api/tablas` | — | Catálogo de fuentes disponibles |
| `GET /api/consulta` | — | Consulta de datos con filtros combinados |
| `GET /api/buscar?q=` | — | Búsqueda de texto completo (FTS5) |
| `GET /api/exportar/{csv\|json}` | — | Exportación de datos filtrados |

### Ejemplos de uso

```bash
# Listar fuentes del censo municipal
curl "http://localhost:8000/api/tablas?censo=CNGMD&por_pagina=5"

# Buscar registros relacionados con agua
curl "http://localhost:8000/api/buscar?q=agua&por_pagina=3"

# Consultar datos del estado de Jalisco
curl "http://localhost:8000/api/consulta?entidad=Jalisco&por_pagina=2"

# Exportar datos federales a JSON
curl "http://localhost:8000/api/exportar/json?censo=CNGF&max_registros=10"
```

### Parámetros comunes

| Parámetro | Tipo | Descripción |
|:----------|:-----|:------------|
| `censo` | string | Filtrar por censo: `CNGF`, `CNGE`, `CNGMD` |
| `nivel` | string | Filtrar por nivel: `federal`, `estatal`, `municipal` |
| `año` | int | Año de publicación |
| `modulo` | string | Módulo temático (búsqueda parcial) |
| `entidad` | string | Entidad federativa (búsqueda parcial) |
| `municipio` | string | Municipio (búsqueda parcial) |
| `clave_geo` | string | Clave geográfica exacta INEGI |
| `pagina` | int | Número de página (por defecto: 1) |
| `por_pagina` | int | Resultados por página (máx: 1000) |

---

## Estructura del proyecto

```
mex-data-hub/
├── api/                  # Servidor FastAPI
│   ├── main.py           # Punto de entrada del servidor
│   ├── routes.py         # Endpoints de la API
│   ├── database.py       # Conexión a SQLite
│   └── models.py         # Modelos de datos
├── ingesta/              # Módulos de procesamiento de datos
│   ├── dbf.py            # Parseo de archivos DBF
│   ├── xlsx.py           # Parseo de archivos XLSX
│   ├── csv_parser.py     # Parseo de archivos CSV
│   ├── descompresor.py   # Extracción de archivos ZIP
│   └── cargador.py       # Carga en SQLite
├── tests/                # Tests automatizados
│   ├── test_dbf.py       # Tests para parser DBF
│   ├── test_xlsx.py      # Tests para parser XLSX
│   ├── test_csv_parser.py
│   ├── test_descompresor.py
│   └── test_integracion.py
├── ingesta.py            # Orquestador de ingesta DBF
├── ingesta_xlsx.py       # Orquestador de ingesta XLSX
├── cargar_sqlite.py      # Script de carga a SQLite
├── optimizar_bd.py       # Optimización de base de datos
├── setup.sh              # Instalación automatizada
├── .github/workflows/    # CI/CD (GitHub Actions)
├── ROADMAP.md            # Ruta de desarrollo
└── requirements.txt      # Dependencias
```

---

## Datos incluidos

Los datos provienen de los **Censos Nacionales de Gobierno** del **INEGI**:

| Censo | Nivel | Periodo | Descripción |
|:------|:------|:--------|:------------|
| CNGF | Federal | 2017–2025 | Gobierno federal, dependencias, presupuesto |
| CNGE | Estatal | 2021–2025 | Gobiernos estatales, administración pública |
| CNGMD | Municipal | 2011–2025 | Municipios, servicios públicos, seguridad |

### Cobertura temática

| Tema | Ejemplos de módulos |
|:-----|:--------------------|
| Estructura organizacional | Organigrama, integrantes, titulares |
| Recursos humanos | Personal, contrataciones, capacitación |
| Recursos materiales | Bienes inmuebles, vehículos, equipo |
| Presupuesto | Ingresos, egresos, deuda pública |
| Servicios públicos | Agua potable, drenaje, residuos, alumbrado |
| Seguridad pública | Policía, justicia cívica, protección civil |
| Transparencia | Acceso a la información, anticorrupción |
| Catastro | Impuesto predial, cartografía, valuación |
| Contrataciones | Adquisiciones, obra pública |
| Programas sociales | Desarrollo social, asistencia |

### Nota sobre años

El año en el nombre del archivo corresponde al **año de publicación**. El período del censo (año al que corresponden los datos) es el año de publicación menos uno. Por ejemplo, `cngf_2017_*` contiene datos del período 2016.

---

## Tests

```bash
python3 -m pytest tests/ -v
```

31 tests que cubren:

- Parseo y decodificación de archivos DBF (CP850, UTF-8)
- Parseo de archivos XLSX en formatos M y temático
- Parseo de archivos CSV con encoding legacy
- Extracción de archivos desde ZIP en múltiples formatos
- Integración del pipeline completo

Los tests utilizan fixtures generados al vuelo y no requieren los archivos originales de INEGI.

---

## Roadmap

| Hito | Estado |
|:-----|:-------|
| Ingesta completa | ✅ |
| API REST | ✅ |
| CI/CD | ✅ |
| Frontend web | 🔴 Pendiente |
| Exportación a redes | 🔴 Pendiente |
| Publicación Zenodo | 🔴 Pendiente |

Ver [ROADMAP.md](ROADMAP.md) para más detalle.

---

## Licencia y atribución

**Código:** Proyecto de código abierto.

**Datos:** © INEGI — Censos Nacionales de Gobierno. El uso de los datos está sujeto a los términos de uso del INEGI. Se permite su uso público con atribución.

**Atribución recomendada:**
> INEGI, Censos Nacionales de Gobierno (CNGF, CNGE, CNGMD). Procesado por la Plataforma de Datos Públicos Mexicanos.

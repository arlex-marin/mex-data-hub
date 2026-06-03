# Roadmap

## Estado actual

| Fase | Estado | Descripción |
|:-----|:------|:------------|
| **Ingesta de datos** | ✅ Completado | Parseo de 245 archivos DBF y 156 archivos XLSX de INEGI |
| **Base de datos SQLite** | ✅ Completado | 7.4M registros cargados, optimizada a 3.4 GB con índice FTS5 |
| **API REST** | ✅ Completado | FastAPI con 6 endpoints y documentación Swagger |
| **CI/CD** | ✅ Completado | GitHub Actions con 31 tests automatizados |
| **Frontend web** | 🔴 Pendiente | Interfaz gráfica para navegar y visualizar los datos |
| **Exportación a redes** | 🔴 Pendiente | Generación de grafos en formato GraphML |
| **Publicación Zenodo** | 🔴 Pendiente | Dataset con DOI para citación académica |

## Próximos hitos

### Fase 2 — Frontend web
- Navegador jerárquico: nivel de gobierno → censo → año → módulo
- Búsqueda con filtros y resultados paginados
- Tableros preconstruidos con gráficas interactivas (Plotly)
- Mapas coropléticos estatales y municipales (Folium)

### Fase 3 — Exportación a redes
- Construcción de grafos multi-nivel desde datos de estructura organizacional
- Exportación a GraphML para análisis con igraph/NetworkX
- Visualización de relaciones intergubernamentales

### Fase 4 — Publicación académica
- Depósito del dataset en Zenodo con DOI permanente
- Documentación para citación en investigaciones

## Metas a largo plazo
- Integración con fuentes de datos adicionales
- Actualización periódica con nuevos censos INEGI
- Versión pública del dataset en acceso abierto

---

*Este roadmap refleja el estado actual del proyecto y está sujeto a cambios según prioridades y disponibilidad de recursos.*

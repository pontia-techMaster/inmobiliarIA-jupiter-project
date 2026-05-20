# Proyecto Júpiter — InmobiliarIA

Repositorio del Trabajo Fin de Máster del Máster en IA, Cloud Computing y DevOps de Pontia.

## Objetivo

Sistema de búsqueda de viviendas mediante **lenguaje natural**. El usuario describe la propiedad que busca con sus propias palabras; el sistema extrae los criterios estructurados, hace una búsqueda semántica con filtros y devuelve los resultados rankeados según las preferencias y su importancia inferida (`hard` vs `soft`).

La ventaja frente a buscadores tradicionales es la **flexibilidad**: viviendas que superan ligeramente algún margen pero cumplen el resto de requisitos siguen apareciendo, con su puntuación ajustada.

## Arquitectura

Sistema *event-driven* en microservicios stateless conectados por colas. Cada servicio escucha de una cola y publica en otra:

```
        ┌────────────┐    SQS:search-requests
        │  frontend  │ ──────────► api_gateway ──────► process_user_prompt
        └────────────┘                                       │
                                                              │ SQS:query-jobs
                                                              ▼
        ┌─────────────────────┐  SQS:rank-jobs   ┌──────────────────┐
        │ ranking_and_         │ ◄────────────── │   vector_query   │
        │   rendering          │                 │  (Qdrant search) │
        └─────────────────────┘                 └──────────────────┘
                  │
                  ├─► SQS:search-responses ──► api_gateway (local) / results-api Lambda (cloud)
                  └─► DynamoDB:user-searches  (historial persistente por usuario)
```

### Servicios de la lógica de negocio

| Servicio | Responsabilidad |
|---|---|
| `data_ingestion` | *Scraping* de HTML, normalización con LLM, vectorización y carga en Qdrant |
| `process_user_prompt` | Extrae campos estructurados del prompt en lenguaje natural usando Gemini + Pydantic |
| `vector_query` | Genera embeddings, construye filtros y busca top-K candidatos en Qdrant |
| `ranking_and_rendering` | Recupera documentos de Qdrant, aplica reglas de scoring y reordena |

### Servicios de soporte

| Servicio | Responsabilidad |
|---|---|
| `api_gateway` | HTTP API (FastAPI local / API Gateway HTTP API en cloud) que recibe el prompt y publica en SQS. Sirve también `GET /results/{id}` (polling) y `GET /users/{id}/searches` (historial) |
| `frontend` | SPA en React con búsqueda, historial lateral, carrusel de fotos, selección múltiple y exportación a PDF |
| `tracer` | (Solo local) UI ligera para inspeccionar logs por `request_id` a través de toda la cadena |
| `results-api` | (Solo cloud) Lambda zip que sirve `GET /results/{id}` y `GET /users/{id}/searches` desde DynamoDB |

### Infraestructura subyacente

- **Colas**: ElasticMQ en local (API compatible con SQS), SQS de AWS en cloud.
- **Base de datos vectorial**: Qdrant local (Docker) en desarrollo, Qdrant Cloud en producción.
- **Base de datos clave-valor**: DynamoDB Local en desarrollo, DynamoDB en cloud.
- **Compute**: docker-compose en local, AWS Lambda (imágenes de contenedor) en cloud.

Detalles del despliegue cloud en [`infra/pulumi/README.md`](infra/pulumi/README.md).

## Uso de modelos

Algunos servicios utilizan IA generativa y búsqueda vectorial. Donde ha sido necesario se ha empleado **LangChain** por su facilidad de uso. Los modelos son los de **Google**:

- `gemini-3.1-flash-lite-preview` — extracción estructurada del prompt y normalización de descripciones.
- `gemini-embeddings-001` — embeddings para la búsqueda vectorial.

> El modelo `gemini-3.1-flash-lite-preview` será renombrado el 20 de mayo de 2026.

## Funcionalidades del frontend

- Búsqueda por lenguaje natural en español.
- **Historial de búsquedas** persistente por usuario (sidebar izquierdo, lista vertical con prompt, número de resultados y tiempo relativo).
- Cada resultado muestra: imágenes en **carrusel**, *score* de relevancia, badges (exterior, ascensor), descripción truncada, enlace al anuncio original.
- **Selección múltiple** con casillas de verificación + **generación de PDF** con los anuncios seleccionados (usa el diálogo nativo de impresión).
- Modo claro/oscuro automático según preferencias del sistema.

## Levantar el entorno local

```bash
# Pre-requisitos: Docker, uv, Node 20+, .env con GEMINI_API_KEY y QDRANT_API_KEY
make up                          # construye y levanta todos los servicios
make trigger-ingestion           # opcional: carga datos de muestra
open http://localhost:5173       # abre el frontend
```

## Desplegar a la nube

CI/CD vía **GitHub Actions** con OIDC contra AWS — sin claves de larga duración. Cada servicio tiene su propio botón "Deploy · `<servicio>`" en la pestaña Actions, más un orquestador `Deploy · all` que despliega todos en el orden correcto. Cada workflow acepta dos inputs:

- `action`: `preview` (dry-run, por defecto) o `up` (aplicar).
- `stack`: `dev`.

Detalles en [`infra/pulumi/README.md`](infra/pulumi/README.md).

## Suite de tests

```bash
uv sync --all-packages --group dev
uv run pytest                    # tests unitarios con cobertura
uv run ruff check .              # lint
uv run black --check .           # formato
uv run mypy .                    # tipos
```

Gate de cobertura en CI: **70%**.

## Estructura del repositorio

```
.
├── services/                    código de cada microservicio
│   ├── api_gateway/             FastAPI + SQS publisher
│   ├── data_ingestion/          scraping + embeddings + carga a Qdrant
│   ├── frontend/                React + Vite + TypeScript
│   ├── process_user_prompt/     Gemini + LangChain → extracción estructurada
│   ├── ranking_and_rendering/   Qdrant fetch + reranking + escritura DDB
│   ├── tracer/                  UI local de tracing
│   └── vector_query/            embeddings + búsqueda Qdrant
├── shared/                      esquemas Pydantic, settings, SQS, DDB helpers
├── infra/pulumi/                stacks Pulumi para AWS (microstack por servicio)
├── tests/                       suite pytest por servicio
├── .github/workflows/           CI (lint, tests, coverage) + deploy workflows
└── Makefile                     atajos locales (up, down, logs, trigger-ingestion, …)
```

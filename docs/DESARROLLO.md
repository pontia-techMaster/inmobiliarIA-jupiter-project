# Guía de desarrollo local

Este documento explica cómo levantar el backend en local, cómo probarlo,
cómo seguir la traza de una búsqueda a través de los microservicios y qué
archivos tocar cuando llegue el momento de implementar cada servicio de
verdad (ahora mismo todos devuelven outputs simulados).

---

## 1. Cómo ejecutar el proyecto

### Requisitos

- Docker Desktop corriendo
- `uv` instalado (`brew install uv` en macOS)
- `make`

### Primera vez

```bash
# Instala dependencias del workspace (shared + todos los servicios)
make sync

# Construye imágenes y levanta todos los contenedores
make up
```

La primera ejecución tarda ~2 minutos (descarga imágenes base y construye
5 imágenes propias). Las siguientes son mucho más rápidas gracias a la
caché de Docker.

### Comandos habituales

| Comando     | Qué hace                                                           |
|-------------|--------------------------------------------------------------------|
| `make up`   | Construye y levanta todos los contenedores                         |
| `make down` | Para y elimina los contenedores                                    |
| `make ps`   | Lista los contenedores y su estado                                 |
| `make logs` | Sigue los logs de todos los contenedores (stream unificado)        |
| `make sync` | Resincroniza el venv del workspace (tras cambiar dependencias)     |

Cuando cambies código de un servicio hay que reconstruir su imagen:

```bash
make up          # ya pasa --build, así que rebuild cacheado
# o, para un solo servicio:
docker compose -f infra/docker-compose.yml up -d --build vector_query
```

### Puertos locales

| Servicio           | Puerto host | Uso                         |
|--------------------|-------------|-----------------------------|
| api_gateway        | 8000        | API HTTP (FastAPI)          |
| frontend           | 5173        | UI React (Vite)             |
| tracer             | 9000        | UI de trazas + JSON         |
| elasticmq (SQS)    | 9324        | API compatible con SQS      |
| elasticmq UI       | 9325        | Estadísticas de las colas   |
| qdrant             | 6333        | API HTTP de Qdrant          |
| qdrant gRPC        | 6334        | API gRPC de Qdrant          |
| dynamodb local     | 8001        | DynamoDB Local              |

---

## 2. Cómo testear

Todos los tests parten de que `make up` dejó la infra corriendo.

### Smoke test de SQS

Verifica que ElasticMQ y el wrapper `shared.sqs` funcionan:

```bash
make smoke
```

Publica un mensaje en `search-requests` y lo lee de vuelta.

### Simulación end-to-end del frontend

Es el test principal: simula lo que hará el FE cuando exista.

```bash
make e2e
```

Hace `POST /search` contra api_gateway, captura el `request_id`, y se
queda escuchando la cola `search-responses` hasta que llega la respuesta
con ese mismo id. La búsqueda recorre los 4 workers.

Salida esperada:

```
posted: {'request_id': '<uuid>'}
waiting for response on search-responses...
{
  "request_id": "<mismo uuid>",
  "results": [
    {"id": "doc-1", "title": "Piso doc-1", "score": 0.9},
    {"id": "doc-2", "title": "Piso doc-2", "score": 0.8}
  ]
}
```

### Probar sólo el api_gateway

```bash
make post-search              # hace POST /search
make peek-search-requests     # consume un mensaje de la cola search-requests
```

### Disparar data_ingestion manualmente

La ingestion acabará siendo una tarea programada (EventBridge en cloud,
cron en local). Para lanzarla a mano:

```bash
make trigger-ingestion
```

Publica un `IngestJob` en `ingest-jobs`; `data_ingestion` lo consume y
loguea `stub handler: would ingest source='/data/html'`.

### Desarrollo con reload del api_gateway

Para iterar rápido en el código del api_gateway sin rebuild de Docker:

```bash
docker compose -f infra/docker-compose.yml stop api_gateway
make api-dev
```

Arranca uvicorn en el host con `--reload`. Necesita la infra (elasticmq,
etc.) corriendo en Docker.

---

## 3. Cómo seguir la traza de una búsqueda

Cada mensaje lleva un `request_id` (UUID generado por api_gateway) que se
propaga por toda la cadena. Los logs incluyen ese id en cada paso, así que
puedes filtrar por él.

### Opción A: Docker Desktop

Abre la pestaña **Logs** de cada contenedor. Para una sola búsqueda verás:

1. **api_gateway**
   ```
   POST /search request_id=<id> prompt='piso en Madrid 2 habitaciones'
   → publish search-requests {"request_id":"<id>",...}
   ```

2. **process_user_prompt**
   ```
   ← consume search-requests {"request_id":"<id>",...}
   stub handler: request_id=<id> prompt='...' → canned fields
   → publish query-jobs {"request_id":"<id>","fields":{...}}
   ```

3. **vector_query**
   ```
   ← consume query-jobs {...}
   stub handler: ... → doc_ids=['doc-1','doc-2']
   → publish rank-jobs {...}
   ```

4. **ranking_and_rendering**
   ```
   ← consume rank-jobs {...}
   stub handler: ... → 2 results
   → publish search-responses {...}
   ```

En el panel de Docker Desktop puedes filtrar por `request_id=<uuid>`.

### Opción B: `make logs`

Fusiona los logs de todos los contenedores en un único stream, prefijados
con el nombre del servicio. Útil cuando quieres ver el orden cronológico
exacto entre contenedores.

### Opción C: UI de ElasticMQ

http://localhost:9325/statistics/queues

Muestra cuántos mensajes hay en cada cola en tiempo real. Útil para
confirmar que no hay mensajes atascados ni colas perdidas.

### Opción D: Servicio `tracer`

http://localhost:9000

Servicio **solo para desarrollo local**. Se conecta al socket de Docker
(`/var/run/docker.sock`) y sigue los logs de todos los contenedores del
proyecto. Cuando ve un `request_id=<uuid>` en una línea, la indexa en
memoria.

- **UI**: http://localhost:9000 — lista de trazas recientes a la
  izquierda, timeline detallado a la derecha. Auto-refresco cada 2 s.
- **Acceso directo a una traza**: http://localhost:9000/?id=<request_id>
  (es a donde apunta el enlace "Ver traza →" del frontend tras enviar
  una búsqueda).
- **API JSON**:
  - `GET /traces` — últimas N trazas con metadatos.
  - `GET /trace/{request_id}` — timeline completo de una petición.

Limitaciones:

- Sólo indexa líneas que contengan `request_id=<uuid>` (ya formateado
  así por todos los workers).
- Es un servicio **local**. En cloud el equivalente es CloudWatch Logs
  Insights con un filtro por `request_id`; el endpoint `/trace/{id}`
  podrá apuntar a esa consulta sin cambiar el frontend.
- Mantiene en memoria las últimas 500 peticiones; al reiniciar pierde
  todo.

---

## 4. Qué tocar para implementar cada servicio

La arquitectura ya está montada: workers, colas, publicación, consumo,
contenedores, logs. Lo único que falta es la lógica real, que ahora
devuelve outputs simulados.

### Convenciones generales

- **No tocar** `worker.py` — es I/O puro (consume cola, llama al handler,
  publica). Se mantiene simple a propósito.
- **Editar** `handler.py` para cambiar la transformación input → output.
- **Rellenar** los módulos vacíos (`llm_client.py`, `embeddings.py`,
  `qdrant_client.py`, `ranker.py`, etc.) con la implementación real.
- Si necesitas dependencias nuevas en un servicio, añádelas en su
  `pyproject.toml` y ejecuta `make sync`.
- Si cambia el esquema de un mensaje, edita `shared/src/shared/schemas.py`.

### Servicio A — `process_user_prompt`

Responsabilidad: dado un `prompt` en lenguaje natural, extraer campos
estructurados con un LLM.

```
services/process_user_prompt/src/process_user_prompt/
├── worker.py        ← NO tocar
├── handler.py       ← sustituir stub por llamada real a llm_client
└── llm_client.py    ← IMPLEMENTAR: wrapper del modelo (ahora vacío)
```

### Servicio B — `vector_query`

Responsabilidad: construir filtros, generar embedding y hacer búsqueda
por similitud en Qdrant.

```
services/vector_query/src/vector_query/
├── worker.py         ← NO tocar
├── handler.py        ← orquestar filters + embeddings + qdrant_client
├── filters.py        ← IMPLEMENTAR: PromptFields → expresión de filtro Qdrant
├── embeddings.py     ← IMPLEMENTAR: texto → vector
└── qdrant_client.py  ← IMPLEMENTAR: similarity search
```

### Servicio C — `data_ingestion`

Responsabilidad: leer HTML, parsearlo, generar embeddings y escribir en
Qdrant. La lógica actualmente vive en
`scripts/extract-property-data.py`, `scripts/generate-summary.py` y
`scripts/generate-embeddings.py`, y habrá que migrarla.

```
services/data_ingestion/src/data_ingestion/
├── worker.py         ← NO tocar
├── handler.py        ← orquestar parser + embeddings + qdrant_client
├── html_parser.py    ← IMPLEMENTAR: HTML → property records
├── embeddings.py     ← IMPLEMENTAR: texto → vector
└── qdrant_client.py  ← IMPLEMENTAR: upsert en Qdrant
```

El volumen `../data/source_html` se monta como `/data/html` en el
contenedor (sólo lectura).

### Servicio E — `ranking_and_rendering`

Responsabilidad: recuperar los documentos completos por id, reordenarlos
según los filtros y devolverlos al FE.

```
services/ranking_and_rendering/src/ranking_and_rendering/
├── worker.py         ← NO tocar
├── handler.py        ← orquestar qdrant_client + ranker
├── qdrant_client.py  ← IMPLEMENTAR: fetch de documentos completos
└── ranker.py         ← IMPLEMENTAR: reordenar por score + filtros
```

### `api_gateway`

Entrypoint FastAPI. Cuando toque, rellenar el cliente de DynamoDB para
`/users`:

```
services/api_gateway/src/api_gateway/
├── main.py           ← FastAPI app; probablemente no hay que tocar
├── routes.py         ← añadir nuevos endpoints aquí
├── sqs_publisher.py  ← (opcional) lógica específica de api_gateway al publicar
└── ddb_client.py     ← IMPLEMENTAR: lectura/escritura de user data en DynamoDB
```

### `shared/`

Código común a todos los servicios. Se toca cuando:

- Cambia el contrato de un mensaje → `shared/src/shared/schemas.py`
- Hay que añadir config nueva (otra cola, otro endpoint) → `shared/src/shared/settings.py`
- El wrapper SQS necesita algo (DLQ, batch, atributos) → `shared/src/shared/sqs.py`

### Añadir un servicio nuevo

1. Crea `services/<nuevo>/` con la misma estructura: `pyproject.toml`,
   `Dockerfile`, `src/<nuevo>/{__init__.py, worker.py, handler.py}`.
2. Añádelo a `infra/docker-compose.yml` con sus env vars.
3. Si necesita una cola nueva, añade el nombre en
   `shared/src/shared/settings.py` y en
   `infra/elasticmq/elasticmq.conf`.
4. `make sync && make up`.

### Referencia rápida de colas

| Cola               | Productor              | Consumidor               | Schema           |
|--------------------|------------------------|--------------------------|------------------|
| `search-requests`  | api_gateway            | process_user_prompt      | `SearchRequest`  |
| `query-jobs`       | process_user_prompt    | vector_query             | `PromptFields`   |
| `rank-jobs`        | vector_query           | ranking_and_rendering    | `RankJob`        |
| `search-responses` | ranking_and_rendering  | frontend (vía Cognito)   | `SearchResponse` |
| `ingest-jobs`      | tarea programada       | data_ingestion           | `IngestJob`      |

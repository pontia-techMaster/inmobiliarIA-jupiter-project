# Servicio `api_gateway`

Puerta de entrada HTTP del sistema. En local es una app FastAPI; en cloud, el `POST /search` lo recibe API Gateway HTTP API directamente (sin pasar por código nuestro) y publica el mensaje en SQS vía integración nativa.

## Responsabilidades

- **Exponer la API REST** que el frontend consume.
- **Traducir requests HTTP a eventos SQS** (`POST /search` → `search-requests`).
- **Servir el polling** del cliente (`GET /results/{id}`) — en local, leyendo de una cache en memoria alimentada por un consumer en background; en cloud, este endpoint lo sirve el stack `results-api`.
- **Exponer el historial por usuario** (`GET /users/{id}/searches`) — local: lee DynamoDB Local; cloud: lo sirve `results-api`.

## Endpoints

### `POST /search`

```jsonc
// Request
{
  "prompt": "Piso luminoso en Madrid, 3 hab, hasta 350k",
  "user_id": "8fd9deec-…",       // opcional; el FE genera y persiste uno en localStorage
  "request_id": "bb070b72-…"     // opcional; si lo manda el cliente, se respeta para trazabilidad
}
```

```jsonc
// Response
{ "request_id": "bb070b72-…" }
```

Publica un `SearchRequest` con `request_id`, `prompt` y `user_id` en SQS `search-requests`. El cliente usa `request_id` para hacer polling.

### `GET /results/{request_id}`

- **200** con el `SearchResponse` completo si ya está listo.
- **404** mientras la búsqueda esté en curso (el FE sigue polleando hasta 90 intentos × 2s).

**Local:** un thread en background consume `search-responses` y guarda cada mensaje en una cache en memoria (`ResultsStore`) con TTL de 10 min.
**Cloud:** ranking_and_rendering escribe el resultado en la tabla DynamoDB `inmo-dev-search-results` (TTL 5 min) y la Lambda `results-api` lo sirve.

### `GET /users/{user_id}/searches?limit=20`

Devuelve hasta `limit` búsquedas más recientes del usuario, ordenadas por timestamp descendente. Lee de la tabla DynamoDB `user-searches` (PK=`user_id`, SK=`request_id`, LSI `by-created-at`).

Schema de cada item:
```jsonc
{
  "user_id": "…",
  "request_id": "…",
  "created_at": 1779270247,
  "prompt": "Piso luminoso en Madrid …",
  "result": { /* SearchResponse completo */ }
}
```

### `GET /health`

Healthcheck simple — `{"status":"ok"}`.

## Variables de entorno

| Variable | Valor por defecto | Notas |
|---|---|---|
| `SQS_ENDPOINT_URL` | `http://localhost:9324` | ElasticMQ local; vacío en cloud para usar el endpoint regional |
| `DYNAMODB_ENDPOINT_URL` | `http://localhost:8001` | DynamoDB Local; vacío en cloud |
| `AWS_REGION` | — | Región AWS |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | — | Credenciales (dummy en local) |
| `QUEUE_SEARCH_REQUESTS` | `search-requests` | Cola de publicación |
| `QUEUE_SEARCH_RESPONSES` | `search-responses` | Cola que consume el background loop |
| `USER_SEARCHES_TABLE` | `user-searches` | Tabla DDB del historial |

## Notas de implementación

- En local el `lifespan` de FastAPI arranca dos cosas no bloqueantes en threads daemon: el consumer de `search-responses` y un `ensure_user_searches_table()` que crea la tabla en DDB Local si no existe.
- En cloud no se levanta esta app — el endpoint `POST /search` es una integración SQS de API Gateway HTTP API, y los GET los sirve `results-api` (Lambda zip).

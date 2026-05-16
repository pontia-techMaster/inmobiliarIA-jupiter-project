# API Gateway - Servicio de Entrada HTTP

Este archivo explica de manera técnica y específica el servicio `api_gateway` del proyecto.

## Propósito y Responsabilidades

El servicio `api_gateway` es la **puerta de entrada HTTP** del sistema.Y suresponsabilidad es:
- **Exponer un API REST** para que el frontend pueda publicar las búsquedas en lenguaje natural
- **Traducir requests HTTP** en eventos SQS para el pipeline asincrónico
- **Proporcionar trazabilidad** a través de `request_id` único
- **Coordinar la comunicación** entre cliente y microservicios backend

### ¿QUÉ HACE?

1. **Expone `POST /search`** que recibe un prompt en lenguaje natural:
   ```python
   POST /search
   {
     "prompt": "Busco piso en Madrid, máx 500k, 3 habitaciones",
     "user_id": "user-123"
   }
   ```

2. **Genera `request_id` único** usando UUID v4:
   ```python
   request_id = uuid.uuid4()  # "7f2a9e1c-4d3b-11ec-81d0-0242ac130003"
   ```

3. **Publica `SearchRequest` en SQS `search-requests`**:
   ```python
   SearchRequest {
     request_id: str, 
     prompt: str,
     user_id: str | None}
   ```

4. **Devuelve inmediatamente `SearchAck`** con el `request_id` al cliente:
   ```json
   {
     "request_id": "7f2a9e1c-4d3b-11ec-81d0-0242ac130003"
   }
   ```
   - El cliente usa este `request_id` para **recuperar resultados después** (polling/websocket)
   - La búsqueda ocurre **asincronamente** en el backend

5. **Expone `GET /health`** para health checks

### ¿Qué NO HACE?

- No procesa el prompt (responsabilidad de `process_user_prompt`)
- No busca en la base vectorial (responsabilidad de `vector_query`)
- No ordena documentos (responsabilidad de `ranking_and_rendering`)
- No almacena datos de usuario (todavía es un stub con `/users/{user_id}`)
- No implementa autenticación/autorización (futura responsabilidad)
- No espera a que termine la búsqueda para responder (es asincrónico)

---

## Arquitectura y Patrones de Diseño

### Patrón de Arquitectura: Request-Reply con SQS

```
┌─────────────┐
│   FRONTEND  │
│  (Cliente)  │
└──────┬──────┘
       │ HTTP POST /search
       │
       ▼
┌──────────────────┐
│  API GATEWAY     │ ← ESTE SERVICIO
│ (FastAPI)        │
│                  │
│ 1. Valida input  │
│ 2. Genera UUID   │
│ 3. Publica SQS   │
│ 4. Responde 202  │
└────────┬─────────┘
         │ Publica SearchRequest
         │
         ▼
    [SQS Queue]
    search-requests
         │
         ├──→ process_user_prompt (consume)
         │
         └──→ Luego a vector_query → ranking_and_rendering
         │
         └──→ Respuesta en search-responses
         │
         ▼
    [SQS Queue]
    search-responses
         │
         └──→ API GATEWAY (consume) → Responde al cliente
         └──→ Frontend (polling/websocket)
```

**Ventajas de este patrón:**
- Desacoplamiento: frontend no espera (no bloquea)
- Escalabilidad: múltiples búsquedas procesadas en paralelo
- Resiliencia: si backend falla, mensajes permanecen en cola
- Trazabilidad: `request_id` visible en todas las capas


### Responsabilidades por Módulo

| Módulo | Responsabilidad | Encapsulación |
|--------|---|---|
| `main.py` | Crear app FastAPI + agregar middleware (CORS) | Exporta solo `app` |
| `routes.py` | Definir endpoints HTTP (/search, /health, /users) | Exporta `router` para incluir en app |
| `sqs_publisher.py` | Abstracción para publicar en SQS | Placeholder, llamada desde routes |
| `ddb_client.py` | Acceso a DynamoDB para datos de usuario | Placeholder, será servicio independiente |

---

## Flujo de Datos Completo

```
1. CLIENT REQUEST (HTTP POST)
   POST /search
   {
     "prompt": "Busco piso en Madrid, máx 500k, 3 habitaciones",
     "user_id": "user-123"
   }

2. routes.search() HANDLER
   ├─ Valida SearchBody con Pydantic
   ├─ Genera request_id = uuid.uuid4()
   ├─ Log: "POST /search request_id=XXX prompt=..."
   └─ Publica en SQS: search-requests
      {
        "request_id": "7f2a9e1c-4d3b-11ec-81d0-0242ac130003",
        "prompt": "Busco piso en Madrid...",
        "user_id": "user-123"
      }

3. IMMEDIATE HTTP RESPONSE (202 Accepted)
   {
     "request_id": "7f2a9e1c-4d3b-11ec-81d0-0242ac130003"
   }
   ← Cliente recibe ID inmediatamente

4. ASYNCHRONOUS PROCESSING (Backend)
   process_user_prompt → vector_query → ranking_and_rendering
   ↓ publica en search-responses

5. CLIENT POLLS OR WEBSOCKET (Futuro)
   GET /search/7f2a9e1c-4d3b-11ec-81d0-0242ac130003
   ↓
   SearchResponse con resultados cuando estén listos
```



## Cómo y Dónde Se Usa

### Flujo Completo (Context Global):

```
┌─────────────────────────────────────────────────────────────────┐
│              FLUJO COMPLETO DE UNA BÚSQUEDA                      │
└─────────────────────────────────────────────────────────────────┘

1️⃣ USUARIO en FRONTEND (http://localhost:5173)
   └─ Input: "Busco piso en Madrid, máx 500k, 3 habitaciones"

2️⃣ FRONTEND hace HTTP request
   POST http://localhost:8000/search
   {
     "prompt": "Busco piso en Madrid...",
     "user_id": "user-123"
   }

3️⃣ API GATEWAY ⭐ (ESTE SERVICIO)
   ├─ Valida SearchBody con Pydantic
   ├─ Genera request_id = "7f2a9e1c-4d3b..."
   ├─ Publica SearchRequest en SQS: search-requests
   └─ Devuelve INMEDIATAMENTE:
      {
        "request_id": "7f2a9e1c-4d3b..."
      }

4️⃣ ASYNCHRONOUS CHAIN (Backend)
   └─ process_user_prompt
      └─ vector_query
         └─ ranking_and_rendering
            └─ Publica SearchResponse en search-responses

5️⃣ FRONTEND (después, cuando esté listo)
   GET /search/7f2a9e1c-4d3b-...
   ↓
   [FUTURO: polling o websocket]
   ↓
   SearchResponse con resultados ordenados
```

### Contratos de Entrada y Salida:

**INPUT (desde Frontend):**
```python
SearchBody {
    prompt: str,
    user_id: str | None
}
```

**OUTPUT (hacia Frontend):**
```python
SearchAck {
    request_id: str
}
```

**OUTPUT (hacia Backend en SQS):**
```python
SearchRequest {
    request_id: str,
    prompt: str,
    user_id: str | None
}
```

### Dónde Se Invoca:

1. **En Local:**
   ```bash
   make api-dev #levanta FastAPI con hot-reload en http://localhost:8000
   ```

2. **En Producción:**
   - Desplegado en ECS/Kubernetes
   - Health check: `GET /health` cada 30 segundos
   - Frontend accede a la URL pública (ej: https://api.example.com)
   - Escalable: múltiples pods detrás de load balancer

3. **Endpoints Principales:**
   - `POST /search` - Publica búsqueda
   - `GET /health` - Health check
   - `GET /users/{user_id}` - Datos usuario (stub actual)

---

## Dependencias Externas

| Servicio/Sistema | Función | Crítico | Fallback |
|---|---|---|---|
| **SQS (AWS)** | Transportar SearchRequest al backend |  SÍ | Si SQS falla, request devuelve error 500 |
| **Frontend** | Cliente HTTP que hace POST /search |  SÍ | Sin frontend, sin requests |
| **process_user_prompt** | Consume SearchRequest y procesa |  SÍ | Si falla, búsqueda queda atrapada en cola |



## Roadmap y Tareas Futuras

- [ ] Implementar autenticación (JWT o similar)
- [ ] Endpoint `GET /search/{request_id}` para recuperar resultados
- [ ] WebSocket para resultados en tiempo real (vs polling)
- [ ] Endpoint `POST /users` para registrar usuarios
- [ ] DynamoDB real para almacenar preferencias de usuario
- [ ] Rate limiting por usuario
- [ ] Logging y métricas a CloudWatch
- [ ] Swagger/OpenAPI documentation

---

## Cómo Ejecutar y Probar

### En Local:

```bash
# Instalar dependencias
make sync

# Levantar contenedor (modo daemon)
make up

# O ejecutar FastAPI con hot-reload (desarrollo rápido)
make api-dev
# → Accesible en http://localhost:8000
# → Swagger docs en http://localhost:8000/docs
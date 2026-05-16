# Explicación del service ranking_and_rendering

Este archivo resume y explica de manera mucho más expecífica y técnica el servicio de `ranking_and_rendering` del proyecto.

## Propósito y Responsabilidades
El servicio `ranking_and_rendeting` es un microservicoi consumidor de eventos que implementa lógica de reordenamiento personalizado y construcción de respuestas para búsquedas inmobiliarias

### ¿QUÉ HACE?

El servicio implementa un **pipeline de reranking personalizado** que toma documentos ya recuperados por búsqueda vectorial y los reordena aplicando lógica de negocio específica. El flujo técnico es:

1. **Consume mensajes `RankJob` de SQS `rank-jobs`** con estructura:
   ```python
   RankJob {
     request_id: str, #identificador único de la búsqueda
     doc_ids: list[str] #IDs de documentos devueltos por vector_query
     doc_scores: list[float], #scores vectoriales (0.0-1.0) de similitud semántica
     fields: list[PromptField] #filtros del usuario estructurados (name, value, strength)
   }
   ```

2. **Recupera documentos completos de Qdrant** usando el patrón **Repository**:
   - Llama a `qdrant_store.get_documents(doc_ids)` que:
     - Mantiene un **cliente Qdrant singleton** (una única conexión TCP reutilizable)
     - Ejecuta `client.retrieve(collection="properties", ids=doc_ids, with_payload=True, with_vectors=False)`
     - Devuelve dict con `id`, `payload` (datos completos de la propiedad) y score

3. **Aplica lógica de ranking compleja** usando patrón **Strategy**:
   - Cada filtro (`price`, `rooms`, `location`, `surface`, `bathrooms`, `has_elevator`, `is_exterior`) es una función independiente
   - Detecta `strength` del filtro:
     - **HARD filters**: Requisito obligatorio. Las propiedades que no cumplen quedan excluidas o penalizadas gravemente
     - **SOFT filters**: Preferencia. Penalizan pero no excluyen
   - Combina puntuación: `score_final = 35% (filtros personalizados) + 65% (score vectorial)`
   - Reordena documentos por score descendente

4. **Construye `SearchResponse`** con patrón **Factory**:
   - Extrae solo los campos necesarios: `id`, `price`, `rooms`, `surface`, `score`
   - Maneja valores faltantes devolviendo `None` (tolerancia a fallos)
   - Preserva `request_id` para trazabilidad end-to-end

5. **Publica en SQS `search-responses`** con formato que el API Gateway puede devolver al cliente inmediatamente**

### ¿Qué es lo que NO hace?
- No realiza búsquedas vectoriales (esto es responsabildad del servicio `vector_query`).
- No ejecuta análisis de prompts (esto es responsabilidad del servicoi `process_user_prompt`).
- No ingesta, procesa ni genera embeddings (responsabilidad del servicio `data_ingestion`).
- No expone una API HTTP directo (solo se comunica vía SQS)
- No almacena estado persistenet (es stateless)
- No realiza transformacion de datos complejas fuera de ranking (es va en los payloads de Qdrant)

## Aquitectura y Patrones de Diseño
En este apartado voy a explicar un poco más y de manera más técnica la arquirtectra del servicio y patrones de diseño usados.

### Patrón de Arquitectura (microservicio basado en eventos)
El servicio sigue un patron `event-driven asíncrono`. Aqui dejo un diagrama sencillo de entender:
````
[API Gateway] 
    ↓ publica RankJob
[SQS: search-requests] 
    ↓ 
[ranking_and_rendering: consumer loop]
    ↓ obtiene documentos
[Qdrant: base vectorial]
    ↓ devuelve payloads completos
[ranking_and_rendering: se realiza lo lógica del ranking]
    ↓ publica SearchResponse
[SQS: search-responses]
    ↓
[API Gateway: devuelve al cliente]
````
**Ventajas de este enfoque:**
- Desacoplamiento total entre los servicios.
- Escalabilidad: múltiples instancias del servicio consumen la misma cola.
- Resilencia si falla, es decir, si un mensaje falla, permanece en la cola para poder hacer reintentos.
- Auditoría, toda la traza de eventos queda en SQS.

### Patrones de Diseño implementados
Aquí mostrare los patrones de diseño usados y la justifación de su uso con las mejoras que implementan en el código

1. **Singleton** para el cliente de Qdrant, de esta manera evitamos crear múltiples conexiones TCP a Qdrant, una única conexión reutlizable para mejorar el rendimiento y sobre todo economizar recursos.

2. **Patrón Repository** para el archivo `qdrant_store.py`, con el objetivo de centralizar y encapsular toda la lógica de acceso a datos. Esto nos faclita el testing y también cambios futuros.

3. **Patrón Strategy** usado en `ranker.py`, cada filtro es independiente. Facilita de esta manera agregar nuevos filtros sin modificar la lógica ya existente. A la vez, en una búsqueda con 10 filtros como la que tenemos, aplicarlos en secuencia es más legible que una mega-función condicional.

4. **Dependencia de injección**, aplciado en el `handler.py`, esto nos permite usar versiones alternativas de funciones. Las dependencias son escplícitas y predecibles.

4. **Patrón Factory**, usado en la construcción del SearchResponse en el `build_response`. Gracias a ello, encapsulamos la lógica de construcción de este objeto de respuesta, de manera que si el esquema del ``SearchResponse` cambia, solo habría que tocar este método.

## Estructura Modular
````
ranking_and_rendering/
├── src/ranking_and_rendering/
│   ├── __init__.py
│   ├── qdrant_store.py          # Repository: acceso a datos
│   ├── ranker.py                # Strategy: lógica de ranking
│   ├── handler.py               # Orquestador principal
│   ├── main.py                  # Punto de entrada (consumer loop)
│   └── schemas.py               # Definiciones Pydantic
├── tests/
│   ├── test_ranker.py           # Tests unitarios
│   ├── test_qdrant_store.py     # Tests de acceso a datos
│   ├── test_handler.py          # Tests de integración
│   └── conftest.py              # Fixtures compartidas
├── pyproject.toml               # Dependencias y configuración
└── Dockerfile                   # Imagen para producción
````

**Responsabilidades de cada módulo**
|modulo|responsabilidad|encapsulacion|
|:----|:----|:----|
|qdrant_store.py|Obtener documentos de Qdrant y gestionar la conexión|Exporta solo get_client() y get_documents()|
|ranker.py|Aplicar filtros| ponderaciones y reordenar documentos|Exporta rank_documents(docs| filters)|
|handler.py|Orquestar el flujo: recuperar → rankear → construir respuesta|Exporta handle_rank_job(job)|
|main.py|Ejecutar el consumer loop de SQS| manejar excepciones y reintentos|Punto de entrada del servicio|
|schemas.py|Definir esquemas Pydantic para validación|Importado por otros módulos|

## Flujo de Datos Completo
````
1. SQS Message (RankJob)
   {
     "request_id": "req-12345",
     "doc_ids": ["doc1", "doc2", "doc3"],
     "filters": {
       "city": "Madrid",
       "price_max": 500000,
       "min_bedrooms": 2
     }
   }

2. handler.py: handle_rank_job()
   ↓
3. qdrant_store.py: get_documents(["doc1", "doc2", "doc3"])
   ↓
4. Qdrant retrieves:
   [
     {"id": "doc1", "payload": {...}, "score": 1.0},
     {"id": "doc2", "payload": {...}, "score": 1.0},
     {"id": "doc3", "payload": {...}, "score": 1.0}
   ]

5. ranker.py: rank_documents(docs, filters)
   - Aplica filtros secuencialmente
   - Modifica scores según criterios
   - Ordena por score descendente
   ↓
6. handler.py: build_response()
   ↓
7. SQS Message (SearchResponse)
   {
     "request_id": "req-12345",
     "results": [
       {
         "id": "doc2",
         "title": "Piso en Madrid",
         "price": 450000,
         "city": "Madrid",
         "score": 1.2,
         ...
       },
       ...
     ],
     "total_count": 3
   }
````

**Las reglas de los filtros están explicadas en su .md específico**

---

## TESTING Explicado

Tenemos una estrategia completa de testing con **cobertura de unitarios, integración y edge cases**. Los tests se encuentran en [tests/ranking_rendering/](tests/ranking_rendering/).

### Test 1: `test_ranking_rendering_qdrant_store.py`

**Responsabilidad:** Validar que la capa de **Repository** (acceso a datos en Qdrant) funciona correctamente y está resiliente.

#### Tests del Patrón Singleton:

```python
def test_get_client_reuses_existing_client():
    """Verifica que el cliente Qdrant se crea UNA SOLA VEZ
    y se reutiliza en llamadas posteriores"""
    
    first_client = qdrant_store.get_client()
    second_client = qdrant_store.get_client()
    
    assert first_client == second_client  # Mismo objeto en memoria
    # QdrantClient.__init__() se llamó solo UNA VEZ
```

**¿Por qué es importante?** 
- Sin Singleton, cada llamada a `get_documents()` abriría una **nueva conexión TCP** a Qdrant
- Múltiples conexiones = desperdicio de recursos + latencia
- Una sola conexión reutilizable = mejor rendimiento + economizar memoria

#### Tests de Llamadas Correctas:

```python
def test_get_documents_calls_retrieve_with_expected_arguments():
    """verifica que get_documents() llama a Qdrant con parámetros correctos"""
    
    result = qdrant_store.get_documents(["prop-1", "prop-2"])
    
    # Verifica que se llamó a:
    # client.retrieve(
    #     collection_name="properties",
    #     ids=["prop-1", "prop-2"],
    #     with_payload=True,      # Necesitamos los datos completos
    #     with_vectors=False,     # NO necesitamos vectores (ahoramos bandwidth)
    # )
```

**¿Por qué es importante?**
- `with_payload=True`: Recupera los datos completos (precio, ubicación, etc.)
- `with_vectors=False`: Ahorra ancho de banda (no enviamos vectores de 1536 dimensiones)
- `collection_name="properties"`: Evita querying en colección equivocada

#### Tests de Manejo de Datos:

```python
def test_get_documents_converts_qdrant_records_to_dicts():
    """Transforma PointStruct de Qdrant en dicts Python"""
    
    # Input desde Qdrant:
    # PointStruct(id="prop-1", payload={"price": 180000, "rooms": 3})
    
    # Output esperado:
    # {"id": "prop-1", "payload": {"price": 180000, "rooms": 3}}
```

**¿Por qué es importante?**
- Qdrant devuelve objetos `PointStruct` (formato interno)
- Los convertimos a dicts para que ranker.py los procese

#### Tests de Tolerancia a Fallos:

```python
def test_get_documents_uses_empty_payload_when_payload_is_none():
    """si Qdrant devuelve payload=None, usamos {} en lugar de fallar"""
    
    result = qdrant_store.get_documents(["prop-1"])
    assert result[0]["payload"] == {}  #no explota, devuelve dict vacío
```

**¿Por qué es importante?**
- Tolerancia a fallos: aunque un documento esté malformado en Qdrant, no crasheamos
- Ranker.py puede usar `.get()` para acceder a campos sin riesgo

```python
def test_get_documents_propagates_qdrant_error():
    """si Qdrant falla, propagamos la excepción para que worker().
    reintente automáticamente"""
    
    with pytest.raises(RuntimeError):
        qdrant_store.get_documents(["prop-1"])  # Qdrant caído = excepción
```

**¿Por qué es importante?**
- Si Qdrant está caído, queremos que SQS **reintente automáticamente** el mensaje
- No queremos silenciar el error (eso sería peor que fallar)

#### Tests de Edge Cases:

```python
def test_get_documents_returns_empty_list_when_no_doc_ids():
    """si no hay IDs, devuelve [] sin hacer I/O innecesaria"""
    
    result = qdrant_store.get_documents([])
    assert result == []
    # get_client() no se llamó: ahorro de CPU
```

**¿Por qué es importante?**
- Optimización: evitamos crear cliente y hacer query si no hay trabajo
- Evita edge case: Qdrant.retrieve(ids=[]) causa error

---

### Test 2: `test_ranking_rendering_ranker.py`

**Responsabilidad:** Validar que la lógica de **Strategy** (cada filtro) funciona correctamente.

```python
def test_hard_field_contributes_full_score():
    """Cuando un filtro es HARD, siempre score=1.0"""
    
    fields = [
        PromptField(name="rooms", value=[3], strength="hard"),
        PromptField(name="price", value=[200000], strength="hard")
    ]
    
    score = _compute_score(payload, fields, semantic_score=1.0)
    assert score ≈ 1.0  # Score máximo porque cumple requisitos HARD
```

```python
def test_soft_rooms_below_requested_penalizes():
    """Cuando es SOFT y no cumple, penaliza pero no excluye"""
    
    score_exact = _compute_score({"rooms": 3}, fields, 0.5)
    score_relaxed = _compute_score({"rooms": 2}, fields, 0.5)
    
    assert score_relaxed < score_exact  # Penalizado
    assert score_relaxed > 0.0  # Pero no excluido
```

---

### Test 3: `test_ranking_rendering_handler.py`

**Responsabilidad:** Validar que el **orquestador** (flujo completo) funciona.

```python
def test_build_result_item_with_full_payload():
    """Extrae campos correctos para el frontend"""
    
    result = handler.build_result_item(doc)
    
    assert result == {
        "id": "prop-1",
        "price": 180000,
        "score": 0.99,  # Score final del ranking
        # ... demas campos
    }
```

```python
def test_build_result_item_without_payload_uses_none_values():
    """Si falta payload, devuelve None en lugar de fallar"""
    
    result = handler.build_result_item({"id": "prop-2"})
    assert result["price"] is None 
```

---

### Resumen: ¿Por qué estos tests?

| Test | Objetivo | Beneficio |
|---|---|---|
| **Singleton** | Una conexión reutilizable a Qdrant | Rendimiento + economía de recursos |
| **Correct Arguments** | Parámetros correctos a Qdrant | Evitar bugs por configuración incorrecta |
| **Data Conversion** | PointStruct → dict | Integración limpia con ranker |
| **Error Propagation** | Fallos se reintenten automáticamente | Resiliencia en producción |
| **Empty Payload** | Tolerancia a datos incompletos | No crashear por malformaciones |
| **Strategy Tests** | Cada filtro funciona independientemente | Fácil agregar nuevos filtros |
| **Handler Tests** | Flujo completo end-to-end | Confianza antes de desplegar |

---

## 🔌 CÓMO Y DÓNDE SE USA

El servicio **NO es autónomo**: forma parte de una cadena de microservicios. Aquí está la integración completa:

### Flujo Completo de una Búsqueda:

```
┌────────────────────────────────────────────────────────────────────┐
│                 FLUJO COMPLETO DE BÚSQUEDA                          │
└────────────────────────────────────────────────────────────────────┘

1️⃣ USUARIO en FRONTEND
   └─ Input: "Busco piso en Madrid, máx 500k, 3 habitaciones"

2️⃣ API GATEWAY
   ├─ Valida entrada
   ├─ Publica en SQS: search-requests
   └─ Responde al cliente: "Procesando..."

3️⃣ PROCESS_USER_PROMPT
   ├─ Interpreta lenguaje natural
   ├─ Extrae: city="Madrid", price_max=500000, rooms=3
   ├─ Crea PromptField[] con strength (hard/soft)
   └─ Publica en SQS: vector-query-jobs

4️⃣ VECTOR_QUERY
   ├─ Genera embeddings del prompt
   ├─ Busca TOP 100 propiedades similares en Qdrant
   ├─ Obtiene IDs + scores vectoriales (0.0-1.0)
   └─ Publica RankJob en SQS: rank-jobs
        {
          "request_id": "req-12345",
          "doc_ids": ["doc1", "doc2", ..., "doc100"],
          "doc_scores": [0.95, 0.92, ..., 0.65],
          "fields": [...]
        }

5️⃣ RANKING_AND_RENDERING ⭐ (ESTE SERVICIO)
   ├─ Consume RankJob de SQS
   ├─ qdrant_store.get_documents(doc_ids) → recupera datos completos
   ├─ ranker.rank(docs, fields) → aplica filtros y reordena
   ├─ handler.build_result_item() → extrae campos para frontend
   ├─ Crea SearchResponse
   └─ Publica en SQS: search-responses
        {
          "request_id": "req-12345",
          "results": [
            {"id": "doc15", "price": 480000, "score": 0.98},
            {"id": "doc2", "price": 450000, "score": 0.87},
            ...
          ]
        }

6️⃣ API GATEWAY (recibe respuesta)
   ├─ Recupera del cache el request original
   ├─ Devuelve JSON al cliente
   └─ Cliente ve propiedades ORDENADAS por relevancia
```

### Contratos entre Servicios:

**INPUT desde `vector_query`:**
```python
RankJob {
    request_id: str
    doc_ids: list[str]
    doc_scores: list[float]
    fields: list[PromptField]
}
```

**OUTPUT hacia `api_gateway`:**
```python
SearchResponse {
    request_id: str #MISMO que input (trazabilidad)
    results: list[Dict] #propiedades ordenadas por relevancia
    # cada resultado contiene: id, price, rooms, surface, score
}
```

### Dónde Se Invoca:

1. **En Local:**
   ```bash
   make up    # Levanta contenedor
   make e2e   # Simula búsqueda completa
   ```

2. **En Producción:**
   - Desplegado en ECS/Kubernetes
   - Escala horizontalmente (múltiples pods)
   - Cada búsqueda → un RankJob → procesado por una instancia
   - Si una instancia falla, otra toma el mensaje de SQS

3. **Monitoreo:**
   - CloudWatch/Datadog: latencia, errores, throughput
   - Alertas: latencia > 2s o error rate > 5%

---

## Roadmap y Tareas Futuras

### Corto Plazo (1-2 sprints)

- [ ] **Calibración de pesos de ranking**
  - Los pesos actuales (35% filtros + 65% vectorial) son valores iniciales
  - Necesita A/B testing real con usuarios para optimizar
  - Métrica: tasa de clicks en resultados TOP 3

- [ ] **Cache de Qdrant**
  - Propiedades populares se consultan múltiples veces por día
  - Implementar Redis para cachear documentos frecuentes
  - TTL: 24 horas (datos inmobiliarios cambian lentamente)
  - Beneficio: -50% latencia en búsquedas comunes

- [ ] **Ampliación de filtros**
  - Agregar nuevos filtros según datos reales de ingesta:
    - `has_terrace` (terraza)
    - `has_garage` (garaje)
    - `has_pool` (piscina)
    - `accessibility_features` (accesibilidad)
  - Actualizar `ranking_rules.py` con nuevas funciones de scoring

### Mediano Plazo (1 mes)

- [ ] **Machine Learning para ranking**
  - Aprender pesos de usuario usando clicks/conversiones
  - Modelo LambdaMART: ranking personalizadopor usuario
  - Training data: logs de búsquedas y clicks en production

- [ ] **Ranking distribuido**
  - Actualmente monolítico en un pod
  - Implementar ranking como servicio escalable independiente
  - Comunicación via gRPC (más rápido que SQS para este caso)

- [ ] **Versionado de estrategias de ranking**
  - Habilitar múltiples versiones simultáneamente
  - Feature flags para activar/desactivar ranking v2
  - Canary deployment: 10% → 50% → 100%

- [ ] **Normalización de scores**
  - Scores actuales pueden estar desbalanceados
  - Implementar min-max normalization (0.0-1.0 real)
  - Útil para explainability al usuario

### Largo Plazo (3+ meses)

- [ ] **Reranking en tiempo real**
  - Incorporar eventos en vivo: nueva property publicada, precio bajó
  - Usar WebSocket para push updates sin polling
  - Mantener resultados "frescos" durante sesión

- [ ] **Explicabilidad (XAI)**
  - Por cada propiedad, mostrar por qué está en esa posición
  - "TOP 1 porque: precio ideal (0.95) + ubicación perfecta (0.92)"
  - Aumenta confianza del usuario en resultados

- [ ] **Multi-objetivo ranking**
  - Actualmente optimizamos solo relevancia
  - Futuro: balancear entre relevancia, rentabilidad, riesgo
  - Para agentes inmobiliarios: ¿cuál es mejor inversión?

- [ ] **Federated ranking**
  - Si hay múltiples fuentes de propiedades (ej: APIs externas)
  - Deduplicar y rankear conjuntamente
  - Mantener score de "confiabilidad de fuente"

### Desafíos Conocidos

1. **Cold Start Problem**
   - Propiedades nuevas tienen score bajo (sin histórico)
   - Solución: boost inicial + decay over time

2. **Filter Hell**
   - Muchos filtros HARD pueden resultar en 0 propiedades
   - Implementar "relax filters" automático: downgrade HARD → SOFT

3. **Score Drift**
   - Pesos fijos pueden no generalizar a nuevos mercados
   - Solución: A/B testing continuo por región

---

## Cómo Ejecutar y Probar

### En Local:

```bash
# Instalar dependencias
make sync

# Levantar stack completo
make up

# Ejecutar tests
pytest tests/ranking_rendering/ -v --cov=src/ranking_rendering

# Consumer en vivo (ver logs)
python -m ranking_and_rendering.worker
```

### E2E Test Manual:

```bash
# Simula búsqueda completa: user → api → prompt → vector → ranking → response
make e2e
```
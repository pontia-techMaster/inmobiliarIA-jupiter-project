# Explicación del Servicio `process_user_prompt`

Este archivo resume y explica de manera técnica el servicio de `process_user_prompt` del proyecto.

## Propósito y Responsabilidades
El servicio `process_user_prompt` es un microservicio consumidor de eventos que implementa la extracción de datos estructurados a partir e una entrada de lenguaje natural. Se encarga de extraer atributos contemplados y su valor, además de información subjetiva que pudiera ser utilizada mediante búsqueda semántica.

### Funcionamiento General del Servicio

El servicio implementa una extracción de datos estructurados usando Langchain y un modelo LLM de Google, inyectando un modelo Pydantic para obligar al modelo a responder bajo un formato estricto. El flujo llevado a cabo dentro del servicio es el siguiente:

1. **Consume mensajes `SearchRequest` de SQS `search-requests`** con estructura:
  ```python
  SearchRequest {
  request_id: str
    prompt: str
    user_id: str | None = None
  }
   ```

2. Utiliza un **LLM con LangChain para extraer información estructurada** con la forma:
  ```python
  ProcessUserPromptOutput {
    fields: list[PromptField] # lista de objetos PromptField (se explica a continuación)
    extra_info: str # información subjetiva
  }
  ```

3. **Aplica lógica de ranking compleja** :
   - Cada filtro (`price`, `rooms`, `location`, `surface`, `bathrooms`, `has_elevator`, `is_exterior`) es una función independiente.
   - Aplica la lógica en función de su dureza (`strength`):
     - **HARD filters**: Requisito obligatorio. Las propiedades que no cumplen quedan excluidas.
     - **SOFT filters**: Preferencia. Penalizan pero no excluyen.
   - Combina puntuación: `score_final = 90% (filtros personalizados) + 10% (score vectorial)`.
   - Reordena documentos por score descendente.

4. Publica un mensaje **ProcessUserPromptResponse** en SQS `query-jobs` con los campos extraídos y la información semántica.

## Campo extraído: `PromptField`

De cada campo que se extrae se debe disponer de la siguiente información:

- `name`: Nombre del campo.
- `value`: lista de posibles valores extraídos.
- `strength`: dureza inferida.
- `extraction_context`: contexto de extracción del campo.

Para el nombre del campo se ofrece al LLM una lista de campos posibles. Estos campos son:

- `property_type`
- `price`
- `surface`
- `rooms`
- `bathrooms`
- `is_exterior`
- `has_elevator`
- `location`

Una de las instrucciones que tiene el LLM es devolver siempre una lista de posibles valores. Es una forma de normalizar para el caso en que el usuario ofrece más de un valor para el mismo campo. Posteriormente se aplica un preprocesamiento específico a cada uno de los campos. 

Un ejemplo. El usuario indica "... de 3 o 4 habitaciones ...". En este caso el valor de salida será `{"name": "rooms", "value": [3, 4], ...}`. Para el campo `rooms` se establece la lógica de coger el valor mínimo de los ofrecidos. Sin embargo, para el campo `location` se usarían todos los valores propuestos.

El atributo `strength` es un parámetro cuyo valor es responsabilidad del LLM y define con qué dureza el usuario ha especificado ese criterio. Si el usuario hace referencia a términos como "sí o sí debe ..." o "es imprescindible que ...", el modelo inferirá una dureza `hard`; en caso contrario, `soft`. El valor de este atributo es posteriormente utilizado para construir los filtros y aplicar reglas de puntuación (el sistema debe ajustarse lo máximo posible a las condiciones impuestas por el usuario, pudiendo diferenciar preferencias de obligaciones).

El campo `extraction_context` es un campo puramente para *debugging* y define el contexto por el cual el modelo ha inferido ese campo y su valor.

Revisar `system-prompt.md` y `shared/schemas.json` para tener más información sobre el prompt utilizado y las restricciones del modelo.

## Variables de Entorno

| Variable | Valor por defecto | Notes |
|--|--|--|
| `SQS_ENDPOINT_URL`        | `http://localhost:9324`   | Endpoint de SQS |
| `AWS_REGION`              | None                      | Región AWS |
| `AWS_ACCESS_KEY_ID`       | None                      | AWS Access Key ID |
| `AWS_SECRET_ACCESS_KEY`   | None                      | AWS Secret Acess Key |
| `QUEUE_SEARCH_REQUESTS`   | `search-requests`         | Nombre de la cola de consumo |
| `QUEUE_QUERY_JOBS`        | `query-jobs`              | Nombre de la cola de publicación |
| `GEMINI_API_KEY`          | None                      | API KEY de Gemini |
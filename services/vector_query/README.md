# Explicación del Servicio `vector_query`

Este archivo resume y explica de manera técnica el servicio de `vector_query` del proyecto.

## Propósito y Responsabilidades
El servicio `vector_query` es un microservicio consumidor de eventos que implementa la lógica de búsqueda en base de datos vectorial, utilizando vectorización y composición de filtros de metadatos.

### Funcionamiento General del Servicio

El flujo del servicio es el siguiente:

1. **Consume mensajes `ProcessUserPromptResponse` de SQS `query-jobs`** con estructura:
   ```python
   ProcessUserPromptResponse {
     request_id: str, # identificador único de la búsqueda
     prompt: str, # input original del usuario
     fields: list[PromptField] # filtros del usuario estructurados (name, value, strength)
     extra_info: str # información extra subjetiva extraída
   }
   ```

2. **Genera embeddings** del campo `extra_info` mediante LangChain y el modelo de embeddings de Google (`gemini-embeddings-001`).

3. **Construye los filtros para Qdrant** usando los campos extraídos en el servicio anterior y aplicando reglas específicas para cada uno.

4. Realiza la **búsqueda por similitud sobre Qdrant** usando los vectores y los filtros de metadatos.

4. Publica un mensaje `RankJob` en SQS `rank-jobs`, con los IDs de los documentos extraídos, su puntuación semántica, y los campos propagados (`prompt`, `user_id`) que `ranking_and_rendering` necesitará para escribir la entrada en el historial del usuario:

   ```python
   RankJob {
     request_id: str
     doc_ids: list[int | UUID | str]
     doc_scores: list[float]
     fields: list[PromptField]
     prompt: str                # propagado end-to-end
     user_id: str | None        # propagado end-to-end
   }
   ```

## Reglas de Construcción de Filtros

A continuación se explica la lógica definida para cada uno de los atributos.

### Tipo de propiedad — `property_type`

Se buscarán viviendas cuyo valor coincida con alguno de los valores aportados por el usuario. Es decir, se aplicará una cláusula OR.

### Localización — `location`

Se procesa cada uno de los valores por separado y se resuelve la localización usando **rapidfuzz**. Cada localización resuelta se procesa:

- Si es **`hard`**:
  - Si la localización resuelta es de tipo *neighborhood*, se toma el valor y se añade a la lista de valores para *neighborhood*.
  - Si la localización resuelta es de tipo *district*, se toma el valor y se añade a la lista de valores para *district*.
- Si es **`soft`**:
  - Si la localización resuelta es de tipo *neighborhood*, se toma el valor del distrito al que pertenece y se añade a la lista de valores para *district*.
  - Si la localización resuelta es de tipo *district*, se toma el valor y se añade a la lista de valores para *district*.

Finalmente se aplica una cláusula OR para cada elemento de las listas, usando la clave *district* o *neighborhood* según corresponda.

**Ejemplo:**

| Valores aportados         | Dureza | Valores resueltos                                                | Filtros                                                              |
|---------------------------|--------|------------------------------------------------------------------|----------------------------------------------------------------------|
| `["Goya", "Carabanchel"]` | Hard   | Goya (`neighborhood`), Carabanchel (`district`)                  | `neighborhood=Goya` OR `district=Carabanchel`                        |
| `["Goya", "Carabanchel"]` | Soft   | Goya (`neighborhood`, parent=`Barrio de Salamanca`), Carabanchel (`district`) | `district=Barrio de Salamanca` OR `district=Carabanchel` |

### Número de habitaciones — `rooms`

Se procesa la entrada y se toma el valor mínimo de los proporcionados (el menos restrictivo).

- **Hard**: se buscan viviendas con valor **≥** al proporcionado.
- **Soft**: se buscan viviendas con valor **≥** al proporcionado aplicando un factor de corrección de **-1**.

### Número de baños — `bathrooms`

Se aplica exactamente la misma lógica que para el número de habitaciones, con su propio factor de corrección, cuyo valor es igualmente **-1**.

### Superficie — `surface`

Se procesa la entrada y se toma el valor mínimo de los proporcionados (el menos restrictivo).

- **Hard**: se buscan viviendas con valor **≥** al proporcionado.
- **Soft**: se aplica un factor de corrección porcentual y se utiliza el valor resultante para aplicar un filtro **≥**.

El nuevo valor se calcula con la fórmula:

$`
\text{relaxed\_value} = \text{value} \times (1 - \text{COEF})
`$

donde el coeficiente para este campo se ha fijado en **15%**.

### Precio — `price`

Se procesa la entrada y se toma el valor máximo de los proporcionados (el menos restrictivo). Se aplica la misma lógica que para la superficie, pero el filtro utilizado es **≤** y el coeficiente se ha fijado en **10%**, sumándose al valor (en lugar de restarse).

### Tiene ascensor — `has_elevator`

Se toma el valor `True` únicamente si no hay presencia de `False` (mecanismo de seguridad). En cualquier otro caso, se toma `False`. Se buscarán viviendas cuyo valor sea **exactamente igual** al valor tomado.

### Es exterior — `is_exterior`

Se aplica exactamente la misma lógica que para la presencia o no de ascensor.


## Runtime: worker (local) vs Lambda (cloud)

- **Local (`worker.py`):** `consume(query-jobs) → handle → publish(rank-jobs)` en un bucle infinito.
- **Cloud (`lambda_handler.py`):** al cold-start resuelve `GEMINI_API_KEY` y `QDRANT_API_KEY` desde SSM Parameter Store antes de importar `handler.py` (los clientes de LangChain y Qdrant validan las keys al construirse).

## Variables de Entorno

| Variable | Valor por defecto | Notas |
|---|---|---|
| `SQS_ENDPOINT_URL` | `http://localhost:9324` | ElasticMQ local; vacío en cloud |
| `AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | — | Credenciales (dummy en local) |
| `QUEUE_QUERY_JOBS` | `query-jobs` | Cola de consumo |
| `QUEUE_RANK_JOBS` | `rank-jobs` | Cola de publicación |
| `QDRANT_URL` | `http://localhost:6333` | Endpoint de Qdrant |
| `QDRANT_API_KEY` | — | Vacío en local (Qdrant Docker sin auth); requerido en cloud (Qdrant Cloud) |
| `QDRANT_COLLECTION` | `properties` | Nombre de la colección |
| `QDRANT_TOP_K` | `10` | Número de candidatos devueltos |
| `GEMINI_API_KEY` | — | API key de Gemini |
| `GEMINI_API_KEY_PARAM` / `QDRANT_API_KEY_PARAM` | — | (Solo cloud) nombres de los SSM parameters |

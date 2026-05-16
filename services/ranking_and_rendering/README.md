# Explicación del Servicio `ranking_and_rendering`

Este archivo resume y explica de manera técnica el servicio de `ranking_and_rendering` del proyecto.

## Propósito y Responsabilidades
El servicio `ranking_and_rendering` es un microservicio consumidor de eventos que implementa lógica de reordenamiento personalizado para búsquedas inmobiliarias, aplicando reglas específicas para cada uno de las condiciones solicitadas por el usuario.

### Funcionamiento General del Servicio

El servicio implementa un **pipeline de reranking personalizado** que toma documentos ya recuperados por búsqueda vectorial y los reordena aplicando lógica de negocio específica. El flujo técnico es:

1. **Consume mensajes `RankJob` de SQS `rank-jobs`** con estructura:
   ```python
   RankJob {
     request_id: str, # identificador único de la búsqueda
     doc_ids: list[str] # IDs de documentos devueltos por vector_query
     doc_scores: list[float], # scores vectoriales (0.0-1.0) de similitud semántica
     fields: list[PromptField] # filtros del usuario estructurados (name, value, strength)
   }
   ```

2. **Recupera los documentos y sus metadatos de Qdrant** a partir de sus IDs.

3. **Aplica lógica de ranking compleja** :
   - Cada filtro (`price`, `rooms`, `location`, `surface`, `bathrooms`, `has_elevator`, `is_exterior`) es una función independiente.
   - Aplica la lógica en función de su dureza (`strength`):
     - **HARD filters**: Requisito obligatorio. Las propiedades que no cumplen quedan excluidas.
     - **SOFT filters**: Preferencia. Penalizan pero no excluyen.
   - Combina puntuación: `score_final = 90% (filtros personalizados) + 10% (score vectorial)`.
   - Reordena documentos por score descendente.

4. **Almacenamiento de resultados en base de datos**.

### ¿Qué es lo que NO hace?
- No realiza búsquedas vectoriales (esto es responsabildad del servicio `vector_query`).
- No ejecuta análisis de prompts (esto es responsabilidad del servicoi `process_user_prompt`).
- No ingesta, procesa ni genera embeddings (responsabilidad del servicio `data_ingestion`).
- No expone una API HTTP directo.
- No almacena estado persistenet.

## Reglas de Puntuación

La puntuación final de cada vivienda es una puntuación normalizada entre **0 y 1**. Cada atributo tiene un peso específico en la puntuación final. La puntuación proporcionada por la base de datos vectorial respecto a la similitud semántica también contribuye con un **10%** a la puntuación final.

En la tabla se presentan los pesos asignados a cada atributo, que suponen el 90% de la puntuación final.

| Campo                  | Peso                  |
|------------------------|-----------------------|
| Tipo de propiedad      | 0% (sin incidencia)   |
| Localización           | 20%                   |
| Número de habitaciones | 20%                   |
| Número de baños        | 8%                    |
| Superficie             | 15%                   |
| Precio                 | 30%                   |
| ¿Tiene ascensor?       | 4%                    |
| ¿Es exterior?          | 3%                    |

> **Nota:** La lógica de puntuaciones aplica cuando los filtros tienen fuerza de tipo `soft`. Los campos con dureza `hard` se deben cumplir por la propia naturaleza de los filtros, por lo que su puntuación es máxima.

### Tipo de propiedad — `property_type`

No se aplica ninguna puntuación para este campo.

### Localización — `location`

Se resuelven las localizaciones proporcionadas por el usuario. Para cada localización resuelta:

- Si es un **barrio**:
  - Si coincide con el barrio de la vivienda → **1**
  - Si el distrito padre coincide con el distrito de la vivienda → **0.5**
  - En cualquier otro caso → **0**
- Si es un **distrito**:
  - Si coincide con el distrito de la vivienda → **1**
  - Si no → **0**

Se devuelve el **máximo** obtenido entre todas las puntuaciones.

> Cuando se habla de "resolver localizaciones" se hace referencia a la resolución de localizaciones basada en lógica difusa (librería `rapidfuzz`), donde disponemos de todos los barrios de Madrid y el distrito al que pertenecen, con valores normalizados. Se aplica lógica difusa para tolerar cierta incertidumbre en la manera que podría tener el usuario de hacer referencia a una de esas localizaciones normalizadas.

### Número de habitaciones — `rooms`

Se toma el valor mínimo de los proporcionados como referencia.

- Si el número de habitaciones de la vivienda es **≥** al propuesto → **1**
- Si no (es menor, pero ha pasado el filtro `soft` de `propuesto - COEF`) → **0.5**

### Número de baños — `bathrooms`

Se aplica exactamente la misma lógica que para el número de habitaciones.

### Superficie — `surface`

Se toma el valor mínimo de los proporcionados como referencia.

- Si el valor de la vivienda es **≥** al propuesto → **1**
- Si no, se aplica:

$$
\text{score} = 1.0 - \frac{\text{shortfall}}{\text{COEF}} \times 0.5
$$

donde:

$$
\text{shortfall} = \frac{\text{requested} - \text{value}}{\text{requested}}
$$

El *shortfall* define la <u>fracción del valor solicitado que le falta a la vivienda</u>. En el caso límite, el valor máximo de *shortfall* es 0.15, que dividido por el COEF (0.15) provoca una puntuación de **0.5**. Cuanto más se acerque la vivienda a lo solicitado, mayor será la puntuación, garantizando un mínimo de **0.5**.

### Precio — `price`

Se toma el valor mínimo de los proporcionados como referencia.

- Si el precio de la vivienda es **≤** al propuesto → **1**
- Si no, se aplica:

$$
\text{score} = \max\bigl(0.0,\; 1.0 - \text{overshoot}^{0.7}\bigr)
$$

donde:

$$
\text{overshoot} = \frac{\text{value} - \text{requested}}{\text{relaxed} - \text{requested}}
$$

$$
\text{relaxed} = \lfloor \text{requested} \times (1 + \text{COEF}) \rfloor
$$

El *overshoot* define la fracción del margen de relajación ya consumida por el precio de la vivienda: **0** indica que está justo al límite del presupuesto, **1** que está en el máximo del margen. El exponente de **0.7** provoca una caída brusca conforme el precio se acerca al margen.

### Tiene ascensor — `has_elevator`

Puntúa **0** si se ha solicitado ascensor y la vivienda no lo tiene. En cualquier otro caso puntúa **1**.

| ¿Se ha solicitado? | ¿La vivienda tiene ascensor? | Puntuación |
|--------------------|------------------------------|------------|
| ❌                 | ❌                           | 1          |
| ❌                 | ✅                           | 1          |
| ✅                 | ❌                           | 0          |
| ✅                 | ✅                           | 1          |

### Es exterior — `is_exterior`

Se aplica exactamente la misma lógica que al atributo `has_elevator`.

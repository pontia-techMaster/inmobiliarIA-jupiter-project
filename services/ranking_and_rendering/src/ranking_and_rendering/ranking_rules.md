# Explicación del sistema de ranking de propiedades
(Hemos decido mostrarlo en español). 
Este documento explica cómo funciona el sistema de ranking de propiedades dividido en dos archivos:

```text
ranking/
├── __init__.py
├── ranking_rules.py
└── ranker.py
```

El objetivo de esta separación es que el código sea más limpio, mantenible y fácil de ampliar.

---

## 1. Objetivo del ranking

El sistema recibe una lista de documentos, normalmente devueltos por Qdrant u otro sistema de búsqueda vectorial.

Cada documento tiene una estructura parecida a esta:

```python
{
    "score": 0.82,
    "payload": {
        "city": "Salamanca",
        "price": 180000,
        "rooms": 3,
        "surface": 85,
        "property_type": "apartment",
        "has_elevator": True
    }
}
```

El campo `score` representa la puntuación inicial, normalmente la similitud semántica del embedding.

El campo `payload` contiene los datos reales de la propiedad.

El objetivo del ranking es modificar ese `score` inicial según los filtros del usuario.

Por ejemplo:

```python
filters = {
    "city": "Salamanca",
    "max_price": 200000,
    "min_rooms": 3,
    "has_elevator": True
}
```

Si una propiedad cumple bien los filtros, su puntuación sube.

Si una propiedad no cumple algunos filtros, su puntuación baja, una penalización.

---

## 2. Por qué separar en dos archivos

Antes toda la lógica estaba dentro de una única función `rank()`.

Eso hacía que el código creciera mucho, además de  demasiadas clausulas de guardia, liar y compartir responsabilidades:

```python
if city_filter:
    ...

if max_price:
    ...

if min_rooms:
    ...

if has_elevator:
    ...
```

El problema es que, si añadimos más filtros, la función se vuelve cada vez más larga y difícil de mantener.

Por eso pensamos en dividirlo en dos archivos:

### `ranking_rules.py`

Este archivo contiene las reglas de puntuación.

Aquí se define cómo se compara cada filtro y cuánto suma o resta al `score`.

Por ejemplo:

- una regla para coincidencia exacta;
- una regla para valores mínimos;
- una regla para valores máximos;
- una regla para booleanos;
- una regla especial para la planta.

### `ranker.py`

Este archivo contiene la función principal `rank()`.

Su responsabilidad es sencilla:

1. Recibir documentos.
2. Recibir filtros.
3. Aplicar todas las reglas.
4. Ordenar los documentos por puntuación final.

---

## 3. Patrón utilizado

Este diseño se parece a una combinación de varios patrones. Ya que en un principio pensamos en usar Strategy, pero notabamos que no era suficiente o que le faltaba algo. Por tanto optamos a la combinación de los siguientes.

### Strategy Pattern

Cada regla actúa como una estrategia distinta de puntuación.

Por ejemplo:

- `ExactMatchRule` compara textos.
- `MinValueRule` comprueba valores mínimos.
- `MaxValueRule` comprueba valores máximos.
- `BooleanMatchRule` compara valores booleanos.
- `FloorMatchRule` compara plantas.

Cada clase tiene su propia forma de modificar el score.

### Pipeline de reglas

Las reglas se aplican una detrás de otra.

```python
for rule in RANKING_RULES:
    score = rule.apply(score, payload, filters)
```

Esto significa:

> Aplica todas las reglas disponibles al documento actual.

---

## 4. Archivo `ranking_rules.py`

Este archivo define las clases que modifican el score.

---

## 5. Clase `RankingRule`

```python
class RankingRule(Protocol):
    def apply(
        self,
        score: float,
        payload: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> float:
        ...
```

Esta clase funciona como una interfaz.

Define que cualquier regla de ranking debe tener un método llamado `apply()`.

Ese método recibe:

- `score`: la puntuación actual del documento.
- `payload`: los datos de la propiedad.
- `filters`: los filtros del usuario.

Y devuelve:

- el nuevo `score`.

Ejemplo conceptual:

```python
score = rule.apply(score, payload, filters)
```

Gracias a esto, todas las reglas funcionan igual desde fuera, aunque por dentro hagan cosas diferentes.

---

## 6. Función `normalize()`

```python
def normalize(value: Any) -> str:
    return str(value).strip().lower()
```

Esta función normaliza textos para poder compararlos mejor.

Por ejemplo:

```text
" Salamanca " -> "salamanca"
"SALAMANCA" -> "salamanca"
"salAmanca" -> "salamanca"
```

Esto evita errores al comparar valores con mayúsculas, minúsculas o espacios.

---

## 7. Función `is_empty()`

```python
def is_empty(value: Any) -> bool:
    ...
```

Esta función comprueba si un valor debe considerarse vacío.

Considera vacío:

```python
None
""
"   "
[]
```

Pero no considera vacío:

```python
False
0
```

Esto es importante porque un filtro como este es válido:

```python
{
    "has_elevator": False
}
```

Si tratásemos `False` como vacío, no se aplicaría el filtro.

---

## 8. Función `to_float()`

```python
def to_float(value: Any) -> float | None:
    ...
```

Esta función convierte un valor a número decimal de forma segura.

Por ejemplo:

```text
"200000" -> 200000.0
200000 -> 200000.0
None -> None
"abc" -> None
```

Se usa para comparar precios, superficies, habitaciones y baños.

---

## 9. Clase `ExactMatchRule`

```python
@dataclass
class ExactMatchRule:
    filter_key: str
    payload_key: str
    bonus: float
    penalty: float
```

Esta regla sirve para comparar campos de texto donde queremos coincidencia exacta.

Por ejemplo:

```python
ExactMatchRule(
    filter_key="city",
    payload_key="city",
    bonus=0.5,
    penalty=0.2,
)
```

Esto significa:

- mira el filtro `city`;
- mira el campo `city` del payload;
- si coinciden, suma `0.5`;
- si no coinciden, resta `0.2`.

Ejemplo:

```python
filters = {
    "city": "Salamanca"
}
```

```python
payload = {
    "city": "Salamanca"
}
```

Resultado:

```python
score += 0.5
```

Pero si el payload fuese:

```python
payload = {
    "city": "Madrid"
}
```

Resultado:

```python
score -= 0.2
```

### Filtros que usan `ExactMatchRule`

| Filtro | Campo del payload | Bonus | Penalización |
|---|---|---:|---:|
| `city` | `city` | `+0.5` | `-0.2` |
| `neighborhood` | `neighborhood` | `+0.3` | `-0.1` |
| `district` | `district` | `+0.2` | `-0.1` |
| `property_type` | `property_type` | `+0.3` | `-0.2` |
| `property_subtype` | `property_subtype` | `+0.2` | `-0.1` |

---

## 10. Clase `MinValueRule`

```python
@dataclass
class MinValueRule:
    filter_key: str
    payload_key: str
    penalty: float
```

Esta regla sirve para filtros de valor mínimo.

Penaliza cuando el valor real está por debajo del mínimo pedido.

Ejemplo:

```python
MinValueRule(
    filter_key="min_rooms",
    payload_key="rooms",
    penalty=0.2,
)
```

Esto significa:

- mira el filtro `min_rooms`;
- mira el campo `rooms` del payload;
- si la propiedad tiene menos habitaciones de las solicitadas, resta `0.2`.

Ejemplo:

```python
filters = {
    "min_rooms": 3
}
```

```python
payload = {
    "rooms": 2
}
```

Resultado:

```python
score -= 0.2
```

Pero si la propiedad tiene 3 o más habitaciones, no se penaliza.

### Filtros que usan `MinValueRule`

| Filtro | Campo del payload | Penalización |
|---|---|---:|
| `min_price` | `price` | `-0.1` |
| `min_surface` | `surface` | `-0.2` |
| `min_rooms` | `rooms` | `-0.2` |
| `min_bathrooms` | `bathrooms` | `-0.2` |

---

## 11. Clase `MaxValueRule`

```python
@dataclass
class MaxValueRule:
    filter_key: str
    payload_key: str
    penalty: float
```

Esta regla sirve para filtros de valor máximo.

Penaliza cuando el valor real supera el máximo pedido.

Ejemplo:

```python
MaxValueRule(
    filter_key="max_price",
    payload_key="price",
    penalty=0.3,
)
```

Esto significa:

- mira el filtro `max_price`;
- mira el campo `price` del payload;
- si la propiedad supera el precio máximo, resta `0.3`.

Ejemplo:

```python
filters = {
    "max_price": 200000
}
```

```python
payload = {
    "price": 230000
}
```

Resultado:

```python
score -= 0.3
```

### Filtros que usan `MaxValueRule`

| Filtro | Campo del payload | Penalización |
|---|---|---:|
| `max_price` | `price` | `-0.3` |
| `max_surface` | `surface` | `-0.2` |

---

## 12. Clase `BooleanMatchRule`

```python
@dataclass
class BooleanMatchRule:
    filter_key: str
    payload_key: str
    bonus: float
    penalty: float
```

Esta regla sirve para filtros booleanos.

Un filtro booleano solo puede tener valores como:

```python
True
False
```

Ejemplo:

```python
BooleanMatchRule(
    filter_key="has_elevator",
    payload_key="has_elevator",
    bonus=0.3,
    penalty=0.3,
)
```

Esto significa:

- si el usuario quiere ascensor y la propiedad tiene ascensor, suma `0.3`;
- si el usuario quiere ascensor y la propiedad no tiene ascensor, resta `0.3`.

Ejemplo:

```python
filters = {
    "has_elevator": True
}
```

```python
payload = {
    "has_elevator": True
}
```

Resultado:

```python
score += 0.3
```

Pero si:

```python
payload = {
    "has_elevator": False
}
```

Resultado:

```python
score -= 0.3
```

### Filtros que usan `BooleanMatchRule`

| Filtro | Campo del payload | Bonus | Penalización |
|---|---|---:|---:|
| `is_exterior` | `is_exterior` | `+0.3` | `-0.3` |
| `has_elevator` | `has_elevator` | `+0.3` | `-0.3` |

---

## 13. Clase `FloorMatchRule`

```python
@dataclass
class FloorMatchRule:
    filter_key: str = "floor"
    payload_key: str = "floor"
    bonus: float = 0.2
    penalty: float = 0.1
```

Esta regla es especial porque el filtro `floor` puede venir de dos formas.

### Caso 1: una única planta

```python
filters = {
    "floor": "2"
}
```

```python
payload = {
    "floor": "2"
}
```

Resultado:

```python
score += 0.2
```

Si no coincide:

```python
score -= 0.1
```

### Caso 2: varias plantas aceptadas

```python
filters = {
    "floor": ["1", "2", "3"]
}
```

```python
payload = {
    "floor": "2"
}
```

Resultado:

```python
score += 0.2
```

Pero si la propiedad está en la planta `"5"`:

```python
score -= 0.1
```

---

## 14. Lista `RANKING_RULES`

```python
RANKING_RULES = [
    ExactMatchRule(...),
    MaxValueRule(...),
    MinValueRule(...),
    BooleanMatchRule(...),
    FloorMatchRule(),
]
```

Esta lista contiene todas las reglas que se aplicarán a cada documento.

El orden importa solo parcialmente.

En este caso, como todas las reglas suman o restan puntos, el orden no cambia el resultado final.

Pero tenerlas ordenadas por bloques ayuda a entender el sistema:

```text
Localización
Precio
Superficie
Habitaciones y baños
Tipo de inmueble
Planta
Booleanos
```

---

## 15. Archivo `ranker.py`

Este archivo contiene la función principal:

```python
def rank(documents, filters):
    ...
```

Su trabajo es aplicar todas las reglas a cada documento.

### Flujo completo de `rank()`

La función hace esto:

```text
1. Crea una lista vacía llamada ranked.
2. Recorre cada documento.
3. Obtiene el score inicial.
4. Obtiene el payload.
5. Aplica todas las reglas de ranking.
6. Crea una copia del documento con el nuevo score.
7. Añade el documento a ranked.
8. Ordena ranked de mayor a menor score.
9. Devuelve ranked.
```

---

## 16. Ejemplo completo

Supongamos este documento:

```python
doc = {
    "score": 0.80,
    "payload": {
        "city": "Salamanca",
        "neighborhood": "Centro",
        "price": 180000,
        "surface": 85,
        "rooms": 3,
        "bathrooms": 2,
        "property_type": "apartment",
        "property_subtype": "flat",
        "floor": "2",
        "is_exterior": True,
        "has_elevator": True,
    }
}
```

Y estos filtros:

```python
filters = {
    "city": "Salamanca",
    "neighborhood": "Centro",
    "max_price": 200000,
    "min_surface": 80,
    "min_rooms": 3,
    "min_bathrooms": 2,
    "property_type": "apartment",
    "floor": ["1", "2", "3"],
    "is_exterior": True,
    "has_elevator": True,
}
```

El cálculo sería aproximadamente:

```text
Score inicial:                 0.80

city coincide:                +0.50
neighborhood coincide:        +0.30
price no supera máximo:       +0.00
surface cumple mínimo:        +0.00
rooms cumple mínimo:          +0.00
bathrooms cumple mínimo:      +0.00
property_type coincide:       +0.30
floor coincide:               +0.20
is_exterior coincide:         +0.30
has_elevator coincide:        +0.30

Score final:                   2.70
```

---

## 17. Resumen final

Antes teníamos una función grande con toda la lógica mezclada.

Ahora tenemos:

```text
ranking_rules.py
```

Responsable de definir cómo se puntúan los filtros.

```text
ranker.py
```

Responsable de aplicar las reglas y ordenar los documentos.

La idea principal es esta:

```python
for rule in RANKING_RULES:
    score = rule.apply(score, payload, filters)
```

Esto convierte el sistema de ranking en un pipeline de reglas fácil de mantener y ampliar.

---

## 18. Futuro
Más adelante, si el sistema crece mucho, se podría dividir todavía más, pero ahora pensamos que sería innecesario.
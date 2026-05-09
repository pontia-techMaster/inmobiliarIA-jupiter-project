# Informe de avances - Desarrollo del servicio de ranking

Este documento resume el estado actual del servicio `ranking_and_rendering` del proyecto `inmobiliarIA-jupiter-project`, cómo se ha implementado, los problemas que han surgido y las soluciones adoptadas. También detalla las tareas que faltan para una puesta en producción.

## Trabajo realizado

Durante el desarrollo se completó una primera versión funcional del microservicio que consume mensajes `RankJob`, recupera documentos completos de Qdrant, aplica la lógica de reordenamiento y devuelve un `SearchResponse` listo para que el frontend lo muestre. El trabajo se organizó en los siguientes módulos:

- **Cliente de Qdrant (`qdrant_store.py`)**. Se implementó una función `get_client()` que crea un único cliente `QdrantClient` a partir de `settings.qdrant_url`. Otra función, `get_documents(doc_ids)`, recibe una lista de ID y hace una llamada a Qdrant para devolver un diccionario con el `id`, el `payload` —datos completos— y una puntuación base. Inicialmente se usó el parámetro `with_vector=False` en `client.retrieve()`, pero la versión reciente de la librería Qdrant lo renombró a `with_vectors`; se ajustó el código eliminando ese argumento o usando `with_vectors=False`.

- **Lógica de ranking (`ranker.py`)**. A partir de la puntuación de similitud —por defecto `1.0`—, se ajusta el `score` de cada documento según los filtros del usuario. Se añadieron filtros básicos —ciudad, precio máximo/mínimo, habitaciones mínimas— y filtros avanzados aprovechando los campos del `payload`: tipo y subtipo de propiedad, barrio y distrito, superficie, número de baños, planta deseada y booleanos (`is_exterior`, `has_elevator`). Tras aplicar bonificaciones o penalizaciones, se ordenan los documentos por `score` de mayor a menor.

- **Orquestador (`handler.py`)**. Esta función recibe un `RankJob` con `request_id`, `doc_ids` y `filters`. Llama a `get_documents()` para obtener la lista de documentos completos y pasa la lista a `rank()` junto con los filtros. Después construye el `SearchResponse` conservando el `request_id` y ensamblando los campos relevantes —id, título, precio, ciudad, etc.— para el frontend.

- **Pruebas unitarias**. Para validar la lógica se creó un test (`tests/test_ranker.py`) que utiliza `unittest.mock.patch` para simular la respuesta de Qdrant. Se construyó un `RankJob` con filtros concretos, se definió una lista `mock_docs` con documentos de ejemplo y se parcheó `ranking_and_rendering.handler.get_documents` para que devolviera esa lista. El test comprueba que el `request_id` se conserva, que se devuelven todos los resultados y que el primero coincide con la propiedad que más cumple los filtros.

- **Endpoint de pruebas en `api_gateway`**. Para pruebas manuales se añadió en `services/api_gateway/src/api_gateway/routes.py` una ruta opcional `/test-ranking` que acepta un `RankJob` en el cuerpo y llama directamente al `handler`. Esta ruta solo se usa en desarrollo (`make api-dev`) porque en producción el gateway no debe importar directamente otros servicios.

- **Arranque local**. Siguiendo la guía de desarrollo, se utilizó `make sync` para instalar dependencias, `make up` para levantar contenedores —ElasticMQ, Qdrant, DynamoDB local y los microservicios— y `make e2e` para simular una búsqueda completa con datos simulados. Para un desarrollo rápido del API Gateway se usó `make api-dev`, que lanza Uvicorn en el host con recarga automática.

## Problemas encontrados y soluciones

Durante el proceso aparecieron varias incidencias, que se resolvieron de la siguiente manera:

| Problema | Solución |
|---|---|
| Dependencia no encontrada al importar `ranking_and_rendering` desde `api_gateway`. El contenedor del gateway no copia código de otros servicios y su `pyproject.toml` no incluye `ranking_and_rendering`. | Para pruebas se usó `make api-dev`, que ejecuta FastAPI en el entorno del workspace donde están instalados todos los paquetes. En producción se debe mantener la comunicación entre servicios mediante colas SQS y evitar importaciones directas; si se necesitase, habría que copiar el código y declarar la dependencia en el Dockerfile del gateway. |
| Parcheo de `get_documents` en los tests. Al importar `get_documents` directamente en `handler.py`, parchar `ranking_and_rendering.qdrant_client.get_documents` no tenía efecto. | Se parcheó `ranking_and_rendering.handler.get_documents` en los tests para interceptar la función que realmente invoca `handler`, devolviendo los documentos simulados. |
| Error `Unknown arguments: ['with_vector']` en Qdrant. Al actualizar el cliente de Qdrant —versión `>= 1.17`—, el parámetro `with_vector` quedó obsoleto. | Se cambió a `with_vectors=False` o se eliminó el argumento, adaptando el código a la nueva API y eliminando el `AssertionError`. |
| Colección `properties` inexistente (`404`) en Qdrant. Sin ejecutar el servicio de ingesta, Qdrant no tenía ninguna colección. | Para pruebas, se usaron datos simulados (`mock_docs`). Se señaló que la ingesta debe poblar Qdrant antes de lanzar búsquedas reales y se recomendó ejecutar `make trigger-ingestion` cuando se implemente el servicio de ingestión de datos. |

## Tareas pendientes

Aunque se ha implementado la lógica de ranking y se han realizado pruebas locales, aún quedan varias tareas para completar el sistema:

1. **Implementar el servicio de ingesta de datos (`data_ingestion`)**. Es necesario desarrollar las funciones de análisis de HTML, generación de embeddings y escritura en Qdrant. Cuando este servicio esté activo, se creará la colección `properties` y se poblará con datos reales, permitiendo usar Qdrant en producción.

2. **Unificar versiones de Qdrant**. Para evitar advertencias de compatibilidad y problemas con la API, conviene que el servidor y el cliente de Qdrant usen versiones alineadas. Alternativamente, inicializar el cliente con `check_compatibility=False` en `get_client()` mitigará el problema temporalmente.

3. **Ajustar pesos y filtros**. La lógica de ranking actual asigna bonificaciones y penalizaciones estáticas. En producción conviene calibrar estos pesos y quizá introducir filtros adicionales —por ejemplo, terraza, piscina o accesibilidad— según las necesidades del negocio.

4. **Eliminar rutas de prueba del API Gateway**. Una vez desplegado, el gateway solo debe publicar en la cola `search-requests` y consumir `search-responses`. Las rutas de pruebas utilizadas en desarrollo (`/test-ranking`) deben eliminarse para no acoplar el gateway a otros servicios.

5. **Ampliar el API Gateway**. A futuro se deberán añadir rutas para gestionar usuarios, favoritos u operaciones relacionadas con DynamoDB. Esto implica completar el cliente de DynamoDB (`ddb_client.py`) e implementar la lógica en `api_gateway`.

## Cómo ejecutar y probar en local

Para quien necesite replicar el entorno de desarrollo, estos son los comandos principales —descritos en detalle en `docs/DESARROLLO.md`—:

1. Instalar dependencias del workspace:

```bash
make sync
```

2. Levantar toda la infraestructura con Docker:

```bash
make up
```

3. Probar un flujo de búsqueda completo con datos simulados:

```bash
make e2e
```

4. Detener los contenedores o ver los logs:

```bash
make logs
make down
```

5. Para desarrollo rápido del API Gateway —recarga de código en caliente— usar:

```bash
make api-dev
```

## Conclusión

Se ha desarrollado y probado de forma satisfactoria el servicio de ranking y rendering, definiendo la conexión con Qdrant, la lógica de reordenamiento basada en múltiples filtros y un manejador que orquesta el flujo. Las pruebas locales demuestran que el servicio responde correctamente con datos simulados. Para llevar el sistema a producción quedan por implementar la ingesta de datos, ajustar la configuración de Qdrant y refinar las rutas del API Gateway. Con estas tareas completadas, el microservicio podrá integrarse plenamente en la arquitectura del proyecto y manejar búsquedas reales con propiedades almacenadas en la base vectorial.

## Cambios necesarios para producción y funcionamiento completo de ingesta

Una vez que el servicio de ingesta esté implementado y se disponga de datos reales, habrá que realizar varios ajustes para pasar de un entorno de desarrollo a uno de producción estable. Los puntos más relevantes son:

1. **Actualizar la configuración compartida (`shared/settings.py`)**.

2. Añadir el atributo `qdrant_collection_name` con un valor por defecto —por ejemplo, `"properties"`— y permitir sobreescribirlo mediante una variable de entorno. Esto evita errores como el `AttributeError` observado cuando el servicio intentó leer un campo inexistente.

3. Parametrizar la URL del servidor Qdrant y de ElasticMQ para entornos de producción. Las rutas usadas en local (`localhost`) deberán sustituirse por los endpoints de los servicios desplegados en la nube.

4. **Eliminar dependencias y código de pruebas**.

5. Suprimir la ruta `/test-ranking` del API Gateway y cualquier importación directa de `ranking_and_rendering` en `api_gateway`. La comunicación entre servicios debe seguir el patrón de colas SQS: el gateway publica en `search-requests` y consume de `search-responses`.

6. Retirar los datos simulados (`mock_docs`) y la lógica de stubs en `handler.py`; una vez la ingesta pobla la colección `properties`, el cliente de Qdrant devolverá documentos reales.

7. **Revisar el esquema de mensajes**.

8. El esquema `RankJob` utilizado por `vector_query` podría ampliarse para incluir la puntuación de similitud devuelta por Qdrant —campo `score`—. Esto permitiría que el `ranker` combine la puntuación base con los filtros sin tener que asumir un valor fijo de `1.0`.

9. Si el servicio de ingesta añade campos nuevos al `payload` —por ejemplo, `has_terrace`, `has_pool`—, deberán reflejarse en `shared/schemas.py` y en la lógica de ranking para que se puedan aplicar nuevos filtros.

10. **Alinear la versión de Qdrant entre cliente y servidor**.

11. Establecer en el `pyproject.toml` de `ranking_and_rendering` la versión concreta del paquete `qdrant-client` compatible con el servidor que se desplegará en producción. Mantener ambas versiones sincronizadas evitará incompatibilidades como el error del parámetro `with_vector`.

12. **Implementar la ingesta de datos en el flujo CI/CD**.

13. Desplegar el servicio `data_ingestion` de forma que, en la puesta en marcha inicial, cree la colección en Qdrant y la llene con los inmuebles. A partir de entonces, programar ingestas periódicas —por ejemplo, con cron o eventos— para mantener la base vectorial actualizada.

14. Asegurarse de que el despliegue de ingesta se ejecute antes de iniciar `process_user_prompt`, `vector_query` y `ranking_and_rendering`, para evitar errores de colección inexistente.

15. **Ajustar la lógica de ranking para producción**.

16. Revisar y calibrar los pesos de cada filtro en función de pruebas de negocio. En un entorno real, los usuarios pueden valorar más ciertos criterios —precio, barrio, superficie— que otros; estos factores se deben ajustar basándose en métricas y feedback.

17. Incorporar nuevos filtros derivados de los datos reales de ingesta —como terraza, garaje, piscina— y actualizar el `ranker` para que tenga en cuenta estas características.

18. **Completar el API Gateway**.

19. Implementar las rutas necesarias para gestionar usuarios y favoritos, con su correspondiente acceso a DynamoDB a través de `ddb_client.py`.

20. Añadir políticas de autenticación/autorización si el sistema lo requiere, y manejar posibles errores de entrada antes de publicar en la cola.

21. **Optimizar las imágenes Docker para producción**.

22. Verificar que cada Dockerfile copia únicamente el código necesario del servicio correspondiente. En el caso del API Gateway, no se debe incluir el código de `ranking_and_rendering` para reducir el tamaño de la imagen y mantener el desacoplamiento.

23. Configurar variables de entorno y secretos —como claves de AWS— en el orquestador de contenedores —por ejemplo, ECS o Kubernetes— en lugar de hardcodarlos en el repositorio.

24. **Automatizar el despliegue**.

25. Incluir scripts o configuraciones de Terraform/CloudFormation que creen las colas SQS, bases de datos y recursos necesarios. De esta forma, todo el stack se podrá reproducir en diferentes entornos —testing, staging y producción— de manera controlada.

Con estas modificaciones y la ingesta de datos operativa, la arquitectura basada en microservicios podrá manejar peticiones reales: el usuario enviará su búsqueda al API Gateway, la cola `search-requests` desencadenará el flujo de análisis, consulta de embeddings, ranking y respuesta. El sistema devolverá listas de propiedades ordenadas por relevancia usando datos actualizados y filtros configurables.

## Referencias

- [DESARROLLO.md](https://github.com/daniilabradorr/inmobiliarIA-jupiter-project/blob/HEAD/docs/DESARROLLO.md)

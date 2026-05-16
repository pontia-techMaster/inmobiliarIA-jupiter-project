# Proyecto Júpiter - InmobiliarIA

Este repositorio contiene el *codebase* del Trabajo Fin de Máster para el Máster de IA, Cloud Computing y DevOps de Pontia.

## Objetivo

Es un sistema de búsqueda de viviendas mediante lenguaje natural. El sistema extrae los requisitos impuestos por el usuario y realiza una búsqueda intensiva utilizando información semántica (criterios subjetivos) y filtros (traducibles a sentencias SQL). El sistema realiza un *reranking* para ordenar las viviendas extraídas en base a los requisitos impuestos por el usuario y a su importancia inferida.

La principal ventaja de este sistema frente a motores de búsqueda corrientes es la flexibilidad que ofrece al usuario para obtener resultados, evitando que se excluyan viviendas que superar ligeramente algunos de los márgenes impuestos pero que pueden ser de gran interés debido a que cumplen con el resto de requisitos.

## Funcionamiento

El sistema es *event drived*. Se compone de varios servicios que se comunican mediante colas de mensajes. Un servicio escucha y publica en una o varias colas. Se ha adoptado esta arquitectura debido a que el sistema consta de servicios cuya funcionalidad es fácilmente divisible y diferenciable del resto, además de que permiten adoptar la filosofía *stateless*.

El sistema se componene esencialmente de estos servicios:

- Servicio de ingesta de datos, `data_ingestion`. Se encarga de procesar información de una o varias fuentes de datos y de publicarlos en una base de datos vectorial.
- Servicio de procesamiento del mensaje del usuario, `process_user_prompt`. Su cometido es procesar el mensaje crudo del usuario, de lenguaje natural, y obtener información estructurada, mediante el uso de un LLM.
- Servicio de búsqueda vectorial, `vector_query`. Encargado de utilizar la información extraída del usuario para realizar la búsqueda vectorial.
- Servicio de ranking, `ranking_and_rendering`. Su función es utilizar las viviendas encontradas en la búsqueda vectorial y los requisitos del usuario para asociar puntuaciones a cada vivienda y generar un nuevo ranking basado en esta nueva puntuación.

Además se hace uso otros servicios que forman parte de la lógica de negocio desarrollada pero que son necesarios para que el sistema funcione en su conjunto. Estos servicios son:

- Gestor de colas y mensajes. En local usamos ElasticMQ debido a que es compatible con las interfaces de SQS de Amazon, que será el servicio usado en producción.
- Servicio API que actúa como backend para la recepción de mensajes del usuario.
- Un ligero frontend para mejorar la experiencia de usuario.
- DynamoDB como base de datos no relacional, en local y en producción.
- (Local) Qdrant como base de datos vectorial. En producción se hará uso de los servicios de Qdrant Cloud.
- (Debugging) Un servicio de tracing para disponer de los logs de los servicios mencionados anteriormente.

## Uso de Modelos

Algunos de los servicios mencionados hacen uso de modelos relacionados con la IA generativa y la búsqueda vectorial. En todos los casos en los que ha sido necesario, se ha hecho uso de LangChain, debido a su facilidad de manejo y que cumple con las necesidades del proyecto.

Los modelos utilizados han sido los modelos de Google, principalmente por sus buenos resultados y porque ofrecen un tier gratuito bastante generoso. Concretamente, se han utilizado los modelos `gemini-3.1-flash-lite-preview` y `gemini-embeddings-001` como LLM y modelo de embeddings, respectivamente.

> El modelo `gemini-3.1-flash-lite-preview` será renombrado el 20 de mayo de 2026. Habrá que tenerlo en cuenta para futuras iteraciones.
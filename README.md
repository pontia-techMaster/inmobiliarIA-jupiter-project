# Proyecto Júpiter - InmobiliarIA

## Scripts

En este directorio se almacenan scripts que tienen distintas funcionalidades.

- `extract-property-data.py`: script encargado de extraer información estructurada de los archivos HTML fuente.
- `generate-summary.py`: script que procesa las descripciones con LLM para generar un resumen normalizado. 
- `generate-embeddings.py`: script que procesa las descripciones normalizadas y genera embeddings.

### `extract-property-data`

Este script se encarga de leer un directorio completo de archivos HTML para procesarlos, utilizando BeautifulSoup4.

El resultado de este script es el mostrado en `data/parsed-properties.json`. Donde se almacena, entre otro tipo de información, atributos asociados a cada vivienda.

### `generate-summary`

Este script recoge las descripciones extraídas de cada anunciante y se las envía a un LLM para que las resuma.

Se ha utilizado el modelo `gemini-3.1-flash-lite-preview`, que tiene un tier gratuito de 500 peticiones al día y los resultados son bastante decentes pese a ser el modelo más simple. Se ha utilizado LangChain como framework por su fácil desarrollo. El *system prompt* utilizado se encuentra en `prompts/generate-summary-prompt.md`.

El resultado de este script se muestra en `data/normalized-descriptions.json`.

### `generate-embeddings`

Este script genera embeddings de las descripciones normalizadas. Se ha hecho uso del modelo `gemini-embeddings-001` (en modo `retrieval_document`) debido a que ofrece hasta 1000 peticiones diarias de manera gratuita. Al igual que con el modelo LLM de generación de resúmenes, se ha utilizado LangChain como framework.

El resultado de este script se muestra en `data/embeddings.json`.
# Explicación del Servicio `data_ingestion`

Este archivo resume y explica de manera técnica el servicio de `data_ingestion` del proyecto.

## Propósito y Responsabilidades
El servicio `data_ingestion` es un microservicio consumidor de eventos que implementa la ingesta en la base de datos vectorial. En el estado actual el proyecto, la fuente de datos es estática (archivos HTML) pero para futuras veriones se espera poder utilizar APIs de servicios de venta como fuentes de datos.

Este servicio es un servicio que se espera ejecutar bajo demanda, publicando mensajes de ingesta en la cola correspondiente. En futuras versiones este servicio podría ser un cron job que se ejecute cada cierto tiempo, validando posibles duplicados.

### Funcionamiento General del Servicio

El servicio implementa un pipeline de extracción de datos, transformación e ingesta. El flujo llevado a cabo dentro del servicio es el siguiente:

1. **Consume mensajes `IngestJob` de SQS `ingest-jobs`** con estructura:
  ```python
  IngestJob {
    source: str # ruta de archivos
  }
   ```

2. Utiliza BeautifulSoup para hacer *scrapping* de una serie de archivos HTML para **extraer información útil de cada vivienda**: atributos, descripción e imágenes.

3. Hace uso de un LLM de Google con LangChain para la **limpiar y normalizar la descripción de la vivienda** (normalmente inundada de información irrelevante).

4. Vectoriza las descripción normalizada usando LangChain y el modelo de embeddings de Google.

5. Se ingesta la información en la base de datos vectorial, con los embeddings y los metadatos.

## Runtime: worker (local) vs Lambda (cloud)

- **Local (`worker.py`):** consume `ingest-jobs` on-demand. Lanzar manualmente con `make trigger-ingestion` para procesar el directorio `services/data_ingestion/data/source_html/`.
- **Cloud (`lambda_handler.py`):** lo dispara una regla EventBridge (`Mondays 03:00 UTC`) o un mensaje manual a la cola. Por ser el más pesado de los Lambdas, su queue (`ingest-jobs`) tiene `visibility_timeout_seconds=3600` y el Lambda tiene `timeout=600`. La fuente de datos es S3 (`inmo-dev-html-source-<account>`).

Al cold-start resuelve `GEMINI_API_KEY` y `QDRANT_API_KEY` desde SSM. Crea índices de payload en Qdrant (`property_type`, `is_exterior`, `has_elevator`) si no existen — necesarios para que `vector_query` pueda filtrar por esos campos.

## Variables de Entorno

| Variable | Valor por defecto | Notas |
|---|---|---|
| `SQS_ENDPOINT_URL` | `http://localhost:9324` | ElasticMQ local; vacío en cloud |
| `AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | — | Credenciales (dummy en local) |
| `QUEUE_INGEST_JOBS` | `ingest-jobs` | Cola de consumo |
| `QDRANT_URL` | `http://localhost:6333` | Endpoint de Qdrant |
| `QDRANT_API_KEY` | — | Requerido en cloud (Qdrant Cloud) |
| `QDRANT_COLLECTION` | `properties` | Nombre de la colección |
| `GEMINI_API_KEY` | — | API key de Gemini |
| `HTML_SOURCE_BUCKET` | — | (Solo cloud) Bucket S3 con los HTML a procesar |
| `GEMINI_API_KEY_PARAM` / `QDRANT_API_KEY_PARAM` | — | (Solo cloud) nombres de los SSM parameters |
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

## Variables de Entorno

| Variable | Valor por defecto | Notes |
|--|--|--|
| `SQS_ENDPOINT_URL`        | `http://localhost:9324`   | Endpoint de SQS |
| `AWS_REGION`              | None                      | Región AWS |
| `AWS_ACCESS_KEY_ID`       | None                      | AWS Access Key ID |
| `AWS_SECRET_ACCESS_KEY`   | None                      | AWS Secret Acess Key |
| `QUEUE_INGEST_JOBS`       | `injest-jobs`             | Nombre de la cola de consumo |
| `QDRANT_URL`              | `http://localhost:6333`   | Dirección de Qdrant |
| `QDRANT_COLLECTION`       | `properties`              | Nombre de la colección en Qdrant |
| `GEMINI_API_KEY`          | None                      | API KEY de Gemini |
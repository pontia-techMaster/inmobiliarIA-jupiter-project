# Explicación del servicio `api_gateway`

Este archivo resume y explica de manera técnica el servicio de `api_gateway` del proyecto.

## Propósito y Responsabilidades

El servicio `api_gateway` es la **puerta de entrada HTTP** del sistema.Y sus responsabilidades son:
- **Exponer un API REST** para que el frontend pueda publicar las búsquedas en lenguaje natural.
- **Traducir requests HTTP** en eventos SQS para el pipeline asincrónico.
- **Proporcionar trazabilidad** a través de `request_id` único.
- **Coordinar la comunicación** entre cliente y microservicios backend.

### Funcionamiento General del Servicio

El cometido principal de este servicio es exponer un endpoint que ofrezca al usuario la funcionalidad principal del sistema: hacer una búsqueda usando lenguaje natural.

El flujo general es el siguiente:

1. **Expone `POST /search`** que recibe un prompt en lenguaje natural:
   ```python
   POST /search
   {
     "prompt": "Busco piso en Madrid, máx 500k, 3 habitaciones",
     "user_id": "user-123"
   }
   ```

2. **Publica `SearchRequest` en SQS `search-requests`**:
   ```python
   SearchRequest {
     request_id: str, # UUID4 generado
     prompt: str,
     user_id: str | None}
   ```

3. **Devuelve inmediatamente `SearchAck`** con el `request_id` al cliente:
   ```json
   {
     "request_id": "7f2a9e1c-4d3b-11ec-81d0-0242ac130003"
   }
   ```
   - El cliente usa este `request_id` para tener una **referencia de la solicitud** y poder **recuperar los resultados**.
   - La búsqueda ocurre **asíncronamente** en el backend.

## Variables de Entorno

| Variable | Valor por defecto | Notes |
|--|--|--|
| `SQS_ENDPOINT_URL`        | `http://localhost:9324`   | Endpoint de SQS |
| `AWS_REGION`              | None                      | Región AWS |
| `AWS_ACCESS_KEY_ID`       | None                      | AWS Access Key ID |
| `AWS_SECRET_ACCESS_KEY`   | None                      | AWS Secret Acess Key |
| `QUEUE_SEARCH_REQUESTS`   | `search-requests`               | Nombre de la cola de consumo |
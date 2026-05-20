# Servicio `tracer`

**Solo local.** Recolector + UI ligera para inspeccionar los logs de toda la cadena indexados por `request_id`. En cloud su equivalente es CloudWatch Logs Insights — el FE detecta que estamos en cloud y enlaza ahí directamente.

## Por qué existe

Cuando una búsqueda viaja por 5+ servicios vía colas SQS, leer logs servicio-a-servicio es tedioso. Este servicio sube todos los logs de `docker compose` a memoria, los indexa por `request_id`, y los muestra en una UI minimal — clic en un id → ves cronológicamente todo lo que pasó con esa búsqueda.

## Arquitectura

```
docker.sock  ──►  collector.py  ──►  store.py (en memoria, anillo)  ──►  main.py (FastAPI)
                  watch stdout         indexa por request_id            sirve UI + JSON
```

- `collector.py`: usa el SDK de docker para hacer `client.containers.list()` + stream de logs de cada contenedor `inmobiliaria-*`. Por cada línea extrae el `request_id` con un regex (busca UUIDv4 en el texto) y la añade al store.
- `store.py`: estructura en memoria con bucket por `request_id`. Mantiene un máximo de N entradas en LRU para no crecer sin parar.
- `main.py`: FastAPI con `/` (UI estática), `/?id=<request_id>` (deeplink), `/api/recent` (últimos ids vistos), `/api/trace/{id}` (todas las entradas para un id).

## Variables de entorno

| Variable | Valor por defecto | Notas |
|---|---|---|
| `TRACER_MAX_ENTRIES` | `5000` | Cap del store en memoria |

El servicio monta el socket de docker en read-only (`/var/run/docker.sock:/var/run/docker.sock:ro`).

## Local

`make up` lo levanta junto al resto del compose. UI en `http://localhost:9000`. El FE muestra un enlace "Ver traza →" en cada resultado/búsqueda que abre la UI ya filtrada por ese `request_id`.

## Por qué no existe en cloud

Los logs de cada Lambda viven en CloudWatch (`/aws/lambda/inmo-dev-<service>`). Para hacer la misma búsqueda usa Logs Insights con un filtro `@message like /<request_id>/` contra todos los log groups. El FE en cloud detecta que `VITE_TRACER_URL == VITE_API_URL` (porque al frontend stack no le pasamos otra cosa) y los enlaces "Ver traza →" apuntan directamente a la consola de CloudWatch en lugar de a un tracer inexistente.

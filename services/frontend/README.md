# Servicio `frontend`

SPA en **React + Vite + TypeScript**. Es el cliente que el usuario abre en el navegador: introduce una búsqueda en lenguaje natural y ve los resultados.

## Funcionalidades

- **Búsqueda en lenguaje natural** (textarea + botón "Buscar"). Genera un `request_id` UUIDv4 en el cliente y lo manda con el POST para que sea visible desde el principio en el tracer.
- **Identidad anónima por navegador.** Al cargar por primera vez, genera un `user_id` UUIDv4 y lo persiste en `localStorage` (clave `inmo.user_id`). Se envía con cada `POST /search` y se usa para listar el historial.
- **Polling de resultados.** Tras enviar la búsqueda, hace polling a `GET /results/{request_id}` cada 2s (máx 90 intentos = 3 min). Mientras tanto muestra skeletons.
- **Historial lateral** ("Tus búsquedas"). Sidebar izquierdo sticky con una fila por búsqueda — prompt, número de resultados y tiempo relativo. Click en una fila → carga sus resultados sin nuevo POST.
- **Cards de resultado**: imagen en **carrusel** (scroll-snap con prev/next y contador), título sintetizado (tipo · barrio · distrito), specs row (hab · baños · m² · planta), **badges** (Exterior, Ascensor), descripción truncada a 3 líneas, **score** prominente (`Score: 0.98`), enlace al anuncio original.
- **Selección múltiple + exportar PDF.** Cada card tiene un checkbox. "Seleccionar todo" / "Limpiar selección (N)" en el header. "Generar PDF (N)" lanza el diálogo de impresión nativo del navegador con un stylesheet `@media print` que oculta todo lo no seleccionado — los anuncios elegidos quedan listos para "Save as PDF".
- **Tema claro/oscuro** según `prefers-color-scheme`.
- **Responsive**: el sidebar colapsa por encima del contenido principal por debajo de 960px de viewport; el grid de cards pasa a una sola columna en móvil.

## Estructura

```
src/
├── App.tsx          UI completa + lógica de polling + selección + PDF
├── App.css          Estilos: layout 2 columnas, sidebar sticky, carrusel, print
├── main.tsx         Entry point
└── index.html       Shell HTML
```

Una sola fuente de verdad para el shape de los resultados (`Property` en `App.tsx`) — debe mantenerse en sincronía con `ranking_and_rendering.handler.build_result_item`.

## Variables de entorno (build-time, Vite)

| Variable | Valor por defecto | Notas |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | URL del api-gateway. En cloud apunta al endpoint del HTTP API |
| `VITE_TRACER_URL` | `http://localhost:9000` | URL del tracer. En cloud el FE detecta que `VITE_TRACER_URL == VITE_API_URL` y enlaza a CloudWatch Logs Insights en su lugar |

## Local

```bash
cd services/frontend
npm install
npm run dev        # http://localhost:5173 (proxy hacia el api_gateway en :8000)
```

O `make up` desde la raíz levanta el FE junto al resto del compose.

## Cloud

El stack Pulumi `frontend` corre `npm install && npm run build` con `VITE_API_URL` y `VITE_TRACER_URL` apuntando al endpoint del API Gateway (no hay tracer en cloud — el FE lo detecta y enlaza a CloudWatch en su lugar), sube `dist/` a un bucket S3 privado, y lo sirve a través de una distribución de CloudFront con OAC.

**Tras desplegar** hay que **invalidar la cache** del CloudFront para que sirva el nuevo `index.html`:

```bash
aws cloudfront create-invalidation \
  --distribution-id $(pulumi -C infra/pulumi/frontend stack output distribution_id) \
  --paths '/*' --profile inmo
```

O `make fe-invalidate` desde `infra/pulumi/`.

## Tests

El FE no tiene tests automatizados — la verificación es manual (`npm run dev` + interacción en navegador). El backend que consume sí está cubierto por la suite pytest.

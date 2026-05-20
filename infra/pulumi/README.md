# Pulumi microstacks — InmobiliarIA Júpiter

Infraestructura cloud organizada como **stacks pequeños y componibles** — uno por servicio, más fundación + state + OIDC.

## Layout

```
.
├── pyproject.toml             deps compartidas (un solo venv para todos los stacks)
├── uv.lock
├── Makefile                   despliegue one-shot + wrappers por stack
├── _shared/                   helpers: naming, tags, stack refs
├── _bootstrap/                S3 state bucket + DDB lock (backend LOCAL — chicken-and-egg)
├── github-oidc/               IAM OIDC provider + role para GitHub Actions
├── platform/                  SQS · ECR · SSM · CloudWatch · S3 source · DDB users · DDB search-results · DDB user-searches
├── api-gateway/               HTTP API + integración directa SQS
├── results-api/               Lambda zip que sirve GET /results/{id} y GET /users/{id}/searches
├── frontend/                  S3 + CloudFront
├── process-user-prompt/       Lambda + ESM (extracción estructurada con Gemini)
├── vector-query/              Lambda + ESM (búsqueda Qdrant)
├── ranking-and-rendering/     Lambda + ESM (Qdrant fetch + reranking + escritura a DDB)
└── data-ingestion/            Lambda + ESM + EventBridge cron
```

**10 stacks desplegables.** `_bootstrap` y `_shared` son especiales:

- `_bootstrap` usa el backend **LOCAL** de Pulumi (chicken-and-egg: crea el bucket S3 que los demás stacks usan como backend).
- `_shared` no es un stack, es un paquete Python usado por todos vía `import _shared`.

## Dos caminos de despliegue

### Camino A: GitHub Actions (recomendado para deploys normales)

CI usa **OIDC** contra AWS — sin claves de larga duración en GitHub. El stack `github-oidc` crea el role; las variables y secrets del entorno `dev` los introduce un admin del repo una sola vez.

Ver [§ CI/CD setup](#cicd-setup) más abajo.

Workflows en `.github/workflows/`:

| Workflow | Cuándo usarlo |
|---|---|
| `Deploy · platform` | Cuando cambian colas, ECR, SSM o tablas DynamoDB |
| `Deploy · api-gateway` | Cuando cambia el HTTP API o la integración SQS |
| `Deploy · process-user-prompt` / `vector-query` / `ranking-and-rendering` / `data-ingestion` | Cambios en cada Lambda de servicio |
| `Deploy · results-api` | Cambios en el handler de polling/historial |
| `Deploy · frontend` | Cambios en el FE (build + sync a S3) |
| `Deploy · all` | Full-stack en orden de dependencias |

Cada workflow acepta dos inputs:

- `action`: `preview` (dry-run, por defecto) o `up` (aplica los cambios).
- `stack`: `dev`.

### Camino B: Pulumi local (iteración rápida o primer setup)

```bash
cd infra/pulumi
make install            # crea venv con Pulumi + plugins
make state-init         # crea el bucket S3 de estado (solo la primera vez por cuenta)
make login-remote       # cambia el CLI al backend S3 (autodescubre el bucket)

make deploy-all                       # despliegue completo
make up STACK=vector-query            # un solo stack
make preview STACK=vector-query       # dry-run
make outputs STACK=api-gateway        # ver outputs en JSON
```

## CI/CD setup

**One-time, lo hace un admin del repo:**

1. Despliega el stack `github-oidc` localmente (con SSO `inmo`). Si la cuenta ya tiene un proveedor OIDC de GitHub, set `pulumi config set existing_provider_arn '<arn>'` antes de `pulumi up` para reutilizarlo.
2. Captura el `role_arn` que el stack exporta.
3. En GitHub → Settings → Environments → `dev`, configura:
   - Variable `AWS_OIDC_ROLE_ARN` = `role_arn` del paso anterior.
   - Variable `PULUMI_BACKEND_URL` = `s3://inmo-dev-pulumi-state?region=eu-west-1`.
   - Secret `PULUMI_CONFIG_PASSPHRASE` = el passphrase que protege los `encryptionsalt` de los stacks.
4. Lista para usarse: ve a Actions, escoge un workflow y dispara `Run workflow`.

**Trust policy:** el role solo es asumible por workflows ejecutándose en este repo desde **main** (configurable vía `github-oidc:allowed_refs` — soporta `refs/heads/<branch>` y `environment:<env>`).

## Prerequisites (deploy local)

- **AWS CLI** con un perfil SSO llamado **`inmo`** apuntando a la cuenta de despliegue. Los `Pulumi.dev.yaml` referencian este perfil. Sesión SSO ~8h; refrescar con `aws sso login --profile inmo`.

  Primera vez:
  ```bash
  aws configure sso --profile inmo
  # SSO start URL:   https://pontia.awsapps.com/start
  # SSO region:      eu-west-1
  # CLI region:      eu-west-1
  # output format:   json
  # profile name:    inmo
  aws --profile inmo sts get-caller-identity   # confirma cuenta
  ```

- **Pulumi CLI**: `brew install pulumi/tap/pulumi`.
- **Docker** corriendo — los stacks de servicio construyen imágenes Lambda vía `pulumi-docker-build`.
- **Node 20+** — el stack `frontend` corre `npm install && npm run build`.

El target `make check-sso` valida la sesión SSO antes de cada comando cloud.

## Grafo de dependencias entre stacks

```
_bootstrap                                   (S3 state bucket + DDB lock)
    │
github-oidc                                  (IAM role para CI — no depende de nada más)
    │
platform                                     (SQS · ECR · SSM · CloudWatch ·
    │                                         S3 source · DDB users · search-results · user-searches)
    ├── api-gateway                          (HTTP API → SQS:search-requests)
    │       ├── results-api                  (Lambda zip → GET /results/{id} · /users/{id}/searches)
    │       └── frontend                     (S3 + CloudFront, lee endpoint del api-gateway)
    │
    ├── process-user-prompt                  (SQS:search-requests → query-jobs)
    ├── vector-query                         (SQS:query-jobs → rank-jobs + Qdrant)
    ├── ranking-and-rendering                (SQS:rank-jobs → search-responses + Qdrant + DDB writes)
    └── data-ingestion                       (SQS:ingest-jobs + EventBridge cron + S3)
```

## Day-2 ops (Makefile)

| Target | Qué hace |
|---|---|
| `make deploy-all` | Despliegue completo en orden (idempotente) |
| `make destroy-all` | Destrucción en orden inverso (excepto `_bootstrap`); pide confirmación |
| `make prompt-secrets` | Re-pregunta por Gemini/Qdrant keys si siguen siendo `REPLACE_ME` |
| `make show-cloud-resources` | Imprime URLs y deep-links a consola para cada servicio |
| `make aws-logs SERVICE=<name>` | `tail -f` del log group de un Lambda (default `process-user-prompt`) |
| `make fe-invalidate` | Flush manual del cache de CloudFront del FE tras `make up STACK=frontend` |
| `make seed-html` | Sincroniza `services/data_ingestion/data/source_html/` → bucket de ingesta |
| `make trigger-ingestion` | Publica un `IngestJob` para procesar el prefijo S3 a demanda |
| `make check-sso` | Valida la sesión SSO `inmo` |

## Tablas DynamoDB (creadas por `platform`)

| Tabla | PK | SK | Notas |
|---|---|---|---|
| `inmo-dev-users` | `user_id` | — | Stub para un futuro microservicio de usuario |
| `inmo-dev-search-results` | `request_id` | — | TTL 5 min. Escrito por `ranking_and_rendering`, leído por `results-api` para el polling del FE |
| `inmo-dev-user-searches` | `user_id` | `request_id` | Sin TTL — historial persistente. LSI `by-created-at` para listar más recientes primero |

## Añadir un nuevo stack de servicio

1. Copia `process-user-prompt/` a `<service>/`.
2. Edita `Pulumi.yaml` (project name, description).
3. Edita `__main__.py`:
   - Cambia la constante `SERVICE`.
   - Cambia la cola de entrada (`platform.queue_arn("query-jobs")`) y de salida.
   - Ajusta la policy IAM para permisos SQS de esas colas.
4. Añade `Dockerfile.lambda` junto al código (template: `services/process_user_prompt/Dockerfile.lambda`). Claves:
   - `FROM public.ecr.aws/lambda/python:3.12`
   - Instala deps en `${LAMBDA_TASK_ROOT}` vía `uv export → pip`.
   - **Termina con `WORKDIR ${LAMBDA_TASK_ROOT}`** — si no, Lambda peta con `Runtime.InvalidWorkingDir`.
5. Añade `lambda_handler.py` al src del servicio. En el cold-start debe traer secretos de SSM y exportarlos como env vars antes de importar `handler.py`.
6. Configura las env vars del Lambda. Como mínimo:
   - `SQS_ENDPOINT_URL=""` para que `shared/sqs.py` use el SQS real.
   - `QUEUE_<OUTPUT>=<nombre-de-cola>` para cada cola en la que escribe.
7. Añade el servicio a `platform/Pulumi.dev.yaml` `services:` y reaplica `make up STACK=platform` para crear su ECR repo + log group.
8. Crea un workflow nuevo en `.github/workflows/deploy-<service>.yml` (copia uno existente).
9. `make up STACK=<service>` o dispara el workflow.

## Quirks que conviene conocer

- **`AWS_PROFILE=inmo` lo exporta el Makefile.** Con SSO, el Go SDK puede caer silenciosamente al perfil default si `inmo` no está en env.
- **`pulumi-docker-build` (0.0.15) no expone `provenance`/`sbom` como kwargs.** Los pasamos vía `exports=[ExportArgs(raw=…)]` — Lambda solo acepta manifests planos, no el OCI image-index que buildx genera por defecto.
- **`image_uri` del Lambda debe ser `<repo>@<digest>` o `<repo>:<tag>`**, no el combinado `<repo>:<tag>@<digest>` que devuelve `image.ref`. Cada stack de servicio lo construye explícitamente.
- **Cada ECR repo necesita una `RepositoryPolicy`** que permita a `lambda.amazonaws.com` hacer `BatchGetImage` + `GetDownloadUrlForLayer`. Sin esto, `CreateFunction` falla con un críptico "Source image is not valid".
- **CloudFront cachea el FE ~24h en el edge.** Tras desplegar el frontend, `make fe-invalidate` o `aws cloudfront create-invalidation --distribution-id <ID> --paths '/*'` para forzar la actualización.
- **`ingest-jobs` tiene `visibility_timeout_seconds=3600`** (vs 60s las otras colas) porque el Lambda de ingesta tarda hasta 600s y AWS exige timeout ≥ función.
- **`make state-init` y `make destroy-all` están gated** por confirmación tipeada — para no triggerearlos por accidente.
- **El stack `github-oidc` puede reutilizar un OpenIdConnectProvider existente** (límite AWS: uno por URL de issuer por cuenta) — set `github-oidc:existing_provider_arn` en config.

## Tearing down

```bash
make destroy-all     # destruye todo excepto _bootstrap
# No destruyas _bootstrap salvo que quieras volver a empezar:
# se pierde el state que apunta a todo lo demás.
```

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from qdrant_client.models import PayloadSchemaType
from shared.schemas import IngestJob
from shared.settings import settings

from .embeddings import EMBEDDINGS_DIMENSIONALITY, embed_texts
from .extractor import PropertyData, PropertyExtractor
from .normalization import normalize_descriptions

load_dotenv()


logger = logging.getLogger("data_ingestion.handler")

# Checkpoint dir defaults to a path next to the service source (writable in
# local dev), overridable via env var. In AWS Lambda the LAMBDA_TASK_ROOT is
# read-only, so the cloud stack sets DATA_INGESTION_CHECKPOINT_DIR=/tmp/...
service_dir = Path(__file__).parent.parent.parent
CHECKPOINT_DIR = Path(os.environ.get("DATA_INGESTION_CHECKPOINT_DIR", str(service_dir / ".checkpoints")))
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
EXTRACT_CHECKPOINT = CHECKPOINT_DIR / "extract-checkpoint.json"
NORMALIZE_CHECKPOINT = CHECKPOINT_DIR / "normalize-checkpoint.json"
EMBED_CHECKPOINT = CHECKPOINT_DIR / "embed-checkpoint.json"


not_valid_attr = ["description", "id"]


def extract_all(source_dir: Path, force: bool = False) -> list[PropertyData]:

    if EXTRACT_CHECKPOINT.exists() and not force:
        raw = json.loads(EXTRACT_CHECKPOINT.read_text(encoding="utf-8"))
        logger.info(f"Loaded {EXTRACT_CHECKPOINT.name} from checkpoint!")
        return [PropertyData(**p) for p in raw]

    html_files = sorted(source_dir.rglob("*.html"))
    properties: list[PropertyData] = []
    for html in html_files:
        try:
            data = PropertyExtractor(html.as_posix()).extract()
            properties.append(data)
        except Exception as e:
            print(f"[SKIP] {html.name}: {e}")

    EXTRACT_CHECKPOINT.write_text(json.dumps([p.to_dict() for p in properties]))

    return properties


def normalize_all(descriptions: list[str], force: bool = False) -> list[str]:

    if NORMALIZE_CHECKPOINT.exists() and not force:
        raw: list[str] = json.loads(NORMALIZE_CHECKPOINT.read_text(encoding="utf-8"))
        logger.info(f"Loaded {NORMALIZE_CHECKPOINT.name} from checkpoint!")
        return raw

    normalized = normalize_descriptions(descriptions)

    NORMALIZE_CHECKPOINT.write_text(json.dumps(normalized), encoding="utf-8")

    return normalized


def embed_all(descriptions: list[str], force: bool = False) -> list[list[float]]:

    if EMBED_CHECKPOINT.exists() and not force:
        raw = json.loads(EMBED_CHECKPOINT.read_text(encoding="utf-8"))
        logger.info(f"Loaded {EMBED_CHECKPOINT.name} from checkpoint!")
        return raw

    vectors = embed_texts(descriptions)

    EMBED_CHECKPOINT.write_text(json.dumps(vectors), encoding="utf-8")

    return vectors


# Payload indexes vector_query needs to filter on. Qdrant doesn't index
# payload fields by default — filtering on an unindexed field returns
# "Bad request: Index required but not found".
PAYLOAD_INDEXES: list[tuple[str, PayloadSchemaType]] = [
    ("property_type", PayloadSchemaType.KEYWORD),
    ("is_exterior", PayloadSchemaType.BOOL),
    ("has_elevator", PayloadSchemaType.BOOL),
    ("location", PayloadSchemaType.KEYWORD),
    ("district", PayloadSchemaType.KEYWORD),
    ("neighborhood", PayloadSchemaType.KEYWORD),
    ("price", PayloadSchemaType.INTEGER),
    ("rooms", PayloadSchemaType.INTEGER),
    ("surface", PayloadSchemaType.INTEGER),
    ("bathrooms", PayloadSchemaType.INTEGER),
]


def _ensure_payload_indexes(qdrant_client: QdrantClient) -> None:
    """Create payload indexes idempotently. Skips ones that already exist."""
    for field, schema in PAYLOAD_INDEXES:
        try:
            qdrant_client.create_payload_index(
                collection_name=settings.qdrant_collection_name,
                field_name=field,
                field_schema=schema,
            )
            logger.info("created payload index: %s (%s)", field, schema)
        except Exception as e:
            # already exists / 409 — fine
            logger.info("payload index %s skipped: %s", field, str(e).splitlines()[0][:80])


def ingest(properties: list[PropertyData], descriptions: list[str], embeddings: list[list[float]]) -> None:

    qdrant_client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    if not qdrant_client.collection_exists(collection_name=settings.qdrant_collection_name):
        qdrant_client.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config=VectorParams(size=EMBEDDINGS_DIMENSIONALITY, distance=Distance.COSINE),
        )
    _ensure_payload_indexes(qdrant_client)

    points = [
        PointStruct(
            id=prop.idealista_id or prop.id,
            vector=vector,
            payload={**{k: v for k, v in prop.to_dict().items() if k not in not_valid_attr}, "description": desc},
        )
        for prop, desc, vector in zip(properties, descriptions, embeddings, strict=True)
    ]

    qdrant_client.upsert(collection_name=settings.qdrant_collection_name, points=points, wait=True)

    return


def handle(job: IngestJob) -> None:

    source = Path(job.source)

    logger.info("Ingestion initialized")

    # extract property data
    properties = extract_all(source)
    logger.debug("Attributes extracted from properties")

    # normalize description with LLM
    descriptions = [p.description for p in properties]
    normalized_descriptions = normalize_all(descriptions)
    logger.debug("Descriptions normalized with LLM")

    # generate embeddings
    embeddings = embed_all(normalized_descriptions)
    logger.debug("Embeddings generated")

    # upsert to vector store
    ingest(properties, normalized_descriptions, embeddings)
    logger.debug("Embeddings upserted in vector store")

    logger.info("Process finished succesfully!")


if __name__ == "__main__":
    job = IngestJob(source="./data/source_html")
    handle(job)

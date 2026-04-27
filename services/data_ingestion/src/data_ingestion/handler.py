import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from shared.schemas import IngestJob
from shared.settings import settings

from .embeddings import EMBEDDINGS_DIMENSIONALITY, embed_texts
from .extractor import PropertyData, PropertyExtractor
from .normalization import normalize_descriptions

load_dotenv()


logger = logging.getLogger("data_ingestion.handler")

CHECKPOINT_DIR = Path(".checkpoints")
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


def ingest(properties: list[PropertyData], descriptions: list[str], embeddings: list[list[float]]) -> None:

    qdrant_client = QdrantClient(url=settings.qdrant_url)
    qdrant_client.create_collection(
        collection_name=settings.qdrant_collection_name,
        vectors_config=VectorParams(size=EMBEDDINGS_DIMENSIONALITY, distance=Distance.COSINE),
    )

    points = [
        PointStruct(
            id=prop.id,
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

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent

SERVICE_SRC_PATHS = [
    project_root / "shared" / "src",
    project_root / "services" / "api_gateway" / "src",
    project_root / "services" / "data_ingestion" / "src",
    project_root / "services" / "process_user_prompt" / "src",
    project_root / "services" / "ranking_and_rendering" / "src",
    project_root / "services" / "tracer" / "src",
    project_root / "services" / "vector_query" / "src",
]

for path in SERVICE_SRC_PATHS:
    sys.path.insert(0, str(path))

os.environ.setdefault("GOOGLE_API_KEY", "fake-api-key-for-tests")
os.environ.setdefault("GEMINI_API_KEY", "fake-api-key-for-tests")
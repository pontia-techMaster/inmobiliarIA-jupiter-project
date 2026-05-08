import sys
from pathlib import Path
import os
# Agregar los directorios src de los servicios al Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "services" / "data_ingestion" / "src"))
sys.path.insert(0, str(project_root / "services" / "ranking_and_rendering" / "src"))
sys.path.insert(0, str(project_root / "shared" / "src"))
sys.path.insert(0, str(project_root / "embeddings" / "src"))


os.environ.setdefault("GOOGLE_API_KEY", "fake-api-key-for-tests")
os.environ.setdefault("GEMINI_API_KEY", "fake-api-key-for-tests")
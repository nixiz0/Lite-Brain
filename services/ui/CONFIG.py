import os
from pathlib import Path
from dotenv import load_dotenv

# ==== Helper Function ====
def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


# ==== Common paths ====
BASE_DIR = Path(__file__).resolve().parent

# Root directory where uploaded files are stored
UPLOAD_ROOT = Path("data/uploads")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# ==== Docker detection ====
IN_DOCKER = os.path.exists("/.dockerenv") or os.getenv("RUNNING_IN_DOCKER") == "1"

# ==== Env loading ====
# We only load .secret-env outside of Docker to avoid overwriting variables
# already passed by the container.
if not IN_DOCKER:
    secret_env_path = BASE_DIR / ".secret-env"
    if secret_env_path.exists():
        load_dotenv(dotenv_path=secret_env_path, override=False)

# ==== Language Config ====
# Get env var and normalize & Fallback to English if unsupported
SUPPORTED_LANGUAGES = {"en", "fr"}
lang = os.getenv("LANGUAGE", "en").strip().lower()
lang = lang if lang in SUPPORTED_LANGUAGES else "en"
LANGUAGE = lang

# ==== Dev Config ====
# Dev server port (used by Uvicorn / auto-reload)
DEV_PORT = 9010

# ==== Database Config ====
# Clear and centralized fallbacks
HOST_SQLITE_URL   = "sqlite:///./data/app.sqlite"       # host
DOCKER_SQLITE_URL = "sqlite:////app/data/app.sqlite"    # in the container

# Final URL: if DATABASE_URL is defined => this takes priority
if "DATABASE_URL" in os.environ:
    DATABASE_URL = os.environ["DATABASE_URL"]
else:
    DATABASE_URL = DOCKER_SQLITE_URL if IN_DOCKER else HOST_SQLITE_URL

# ==== URLs / Endpoints ====
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

ML_API_URL = os.getenv("ML_API_URL", "http://localhost:9005")
OCR_API_URL = ML_API_URL.rstrip("/") + "/ocr"
EMBED_API_URL = ML_API_URL.rstrip("/") + "/embed"
RERANKING_API_URL = ML_API_URL.rstrip("/") + "/rerank"

OLLAMA_TIMEOUT_S = 600
EMBED_API_TIMEOUT_S = 300
OCR_API_TIMEOUT_S = 300
RERANKING_API_TIMEOUT_S = 300

# ==== LLM models configuration ====
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "qwen3:4b")
TURBO_LLM_MODEL   = os.getenv("TURBO_LLM_MODEL", "qwen3:8b")

ULTRA_MODE_ACTIVE = get_bool_env("ULTRA_MODE_ACTIVE", False)
ULTRA_LLM_MODEL   = os.getenv("ULTRA_LLM_MODEL", "qwen3:14b")

# Max number of messages to keep in conversation history (without the think)
LLM_HISTORY_MAX_MESSAGES = int(os.getenv("LLM_HISTORY_MAX_MESSAGES", 10))

# Convenience mapping by "tier" name
LLM_MODELS_BY_TIER = {
    "default": DEFAULT_LLM_MODEL,
    "turbo": TURBO_LLM_MODEL,
    "ultra": ULTRA_LLM_MODEL,
}

REQUIRED_LLM_MODELS = {DEFAULT_LLM_MODEL, TURBO_LLM_MODEL}
if ULTRA_MODE_ACTIVE:
    REQUIRED_LLM_MODELS.add(ULTRA_LLM_MODEL)

# ==== RAG / document chunking configuration ====
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1200))         # tokens/characters per chunk
OVERLAP = int(os.getenv("OVERLAP", 150))                # overlap between consecutive chunks
TOP_K_HYBRID = int(os.getenv("TOP_K_HYBRID", 64))       # raw candidates fetched from Qdrant
TOP_K_MMR = int(os.getenv("TOP_K_MMR", 16))             # candidates kept after MMR
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", 8))        # final results after reranking
MMR_LAMBDA = float(os.getenv("MMR_LAMBDA", 0.5))        # relevance vs diversity trade-off

# Maximum total number of chunks we're willing to process in full-doc mode.
# This remains a safeguard (to avoid making 10,000 LLM calls).
MAX_FULL_DOC_CHUNKS = int(os.getenv("MAX_FULL_DOC_CHUNKS", 1200))

# Number of chunks per batch for the "map" phase.
# To be adjusted according to the average size of a chunk and the context of the model (4k / 8k).
# For 4k context = 10-12 // For 8k context = 22-24
FULL_DOC_CHUNKS_PER_BATCH = int(os.getenv("FULL_DOC_CHUNKS_PER_BATCH", 12))

# ==== OCR heuristic thresholds ====
MIN_CHAR_PER_PAGE = int(os.getenv("MIN_CHAR_PER_PAGE", 50))        # below → likely needs OCR
AVG_MIN_CHARS = int(os.getenv("AVG_MIN_CHARS", 200))               # minimal avg text per page
BLANK_PAGE_THRESHOLD = float(os.getenv("BLANK_PAGE_THRESHOLD", 0.3))  # ratio for blank page detection


# ==== App Secret Key ====
SECRET_KEY = os.getenv("SECRET_KEY", "SubscribeToHeyInitium<3")

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .secret-env explicitly
load_dotenv(dotenv_path=".secret-env", override=False)

# =====================[ Paths / model cache ]====================
# Folder where this file is located
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", BASE_DIR.parents[1])) # Do like a 'cd ..'

# Project root: by default, the parent of the current folder
MODELS_ROOT = Path(os.getenv("MODELS_ROOT", PROJECT_ROOT / "model"))
MODELS_ROOT.mkdir(parents=True, exist_ok=True)

# Dedicated subfolder for reranking
RERANKING_MODEL_DIR = Path(os.getenv("RERANKING_MODEL_DIR", MODELS_ROOT / "bge-m3-reranking"))
RERANKING_MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_DIR = os.getenv("MODEL_DIR", str(RERANKING_MODEL_DIR))

# =====================[ Auth / runtime ]====================
# Auth (empty => no auth)
API_KEY = os.getenv("API_KEY", "")

# DEVICE = "cpu" or "cuda:0" (or other)
DEVICE = os.getenv("DEVICE", "cpu")

# MAX_WORKERS = number of parallel inference threads
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "2"))

# Threads Torch – adapt to your CPU (4 = good default for a recent i5).
TORCH_NUM_THREADS = int(os.getenv("TORCH_NUM_THREADS", "4"))
TORCH_NUM_INTEROP = int(os.getenv("TORCH_NUM_INTEROP", "1"))

# =====================[ Hugging-Face Model ]====================
RERANK_MODEL_NAME = os.getenv("RERANK_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
MODEL_REVISION = os.getenv("MODEL_REVISION", "main")

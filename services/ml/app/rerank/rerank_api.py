import os, asyncio
import torch
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from huggingface_hub import snapshot_download
from FlagEmbedding import FlagReranker

from .rerank_config import (
    API_KEY,
    DEVICE,
    MAX_WORKERS,
    RERANK_MODEL_NAME,
    MODEL_DIR,
    MODEL_REVISION,
    TORCH_NUM_THREADS,
    TORCH_NUM_INTEROP,
)

# Disable tokenizer parallelism warnings for cleaner logs.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


# -------------- Device Config --------------
def _select_device(device_str: str) -> str:
    """
    If it builds on CUDA and no GPU is detected, then it will remain on the CPU.
    """
    dev = device_str or "cpu"
    if dev.startswith("cuda") and not torch.cuda.is_available():
        print("[RERANK boot] CUDA requested but not available, falling back to CPU.")
        return "cpu"
    return dev

device = _select_device(DEVICE)

# FP16 effective: only if you are actually on CUDA
EFFECTIVE_FP16 = device.startswith("cuda") and torch.cuda.is_available()


# -------------- Global Config --------------
# Configure PyTorch threading based on configuration values.
# If the host doesn't support these options, ignore the error and continue.
try:
    torch.set_num_threads(TORCH_NUM_THREADS)
    torch.set_num_interop_threads(TORCH_NUM_INTEROP)
except Exception:
    # Do not fail the application startup if thread configuration is not supported.
    pass


# -------------------- Configuration --------------------
class Settings(BaseSettings):
    """
    Centralized configuration for the reranker service.
    Values come from rerank_config and can be overridden via environment variables.
    """
    api_key: str = API_KEY
    device: str = DEVICE
    max_workers: int = MAX_WORKERS
    model_name: str = RERANK_MODEL_NAME
    model_dir: str = MODEL_DIR
    model_revision: str = MODEL_REVISION

settings = Settings()

# Ensure model directory exists before loading/downloading the model.
os.makedirs(settings.model_dir, exist_ok=True)


# -------------------- Reranker Model --------------------
reranker: Optional[FlagReranker] = None

# Pool of worker threads that execute blocking model inference without blocking the event loop
executor = ThreadPoolExecutor(max_workers=settings.max_workers)

def _local_model_ready(path: str) -> bool:
    """
    Check if a local model snapshot appears complete:
    - directory exists
    - contains config.json
    - contains at least one weights file (*.bin or *.safetensors)
    """
    if not os.path.isdir(path):
        return False
    entries = set(os.listdir(path))
    has_config = "config.json" in entries
    has_weights = any(fn.endswith((".safetensors", ".bin")) for fn in entries)
    return has_config and has_weights

def _ensure_local_model() -> str:
    """
    Ensure a local model copy exists.
    - If already available, reuse it.
    - Otherwise download the snapshot from the Hugging Face Hub.
    """
    local_dir = settings.model_dir
    os.makedirs(local_dir, exist_ok=True)

    if _local_model_ready(local_dir):
        return local_dir

    print(f"[bge-reranker] Downloading model {settings.model_name} in {local_dir} ...")
    snapshot_download(
        repo_id=settings.model_name,
        revision=settings.model_revision,
        local_dir=local_dir,
        local_dir_use_symlinks=False,
        allow_patterns=[
            "*.json",
            "*.txt",
            "*.md",
            "*.safetensors",
            "*.bin",
            "config.json",
            "tokenizer.*",
            "vocab.*",
            "merges.txt",
            "spiece.*",
            "*.model",
        ],
    )
    print("[bge-reranker] Download complete.")
    return local_dir

def _load_reranker() -> FlagReranker:
    """
    Load the FlagReranker model with appropriate device and FP16 settings.
    """
    local_path = _ensure_local_model()
    
    print(
        f"[bge-reranker] Loading model from {local_path} "
        f"(device={device}, fp16={EFFECTIVE_FP16})..."
    )
    m = FlagReranker(
        local_path,
        use_fp16=EFFECTIVE_FP16,
        device=device,
    )
    print("[bge-reranker] Model loaded.")
    return m

async def get_reranker() -> FlagReranker:
    """
    Lazily load the global reranker instance using a thread pool.
    Ensures the heavy load happens only once.
    """
    global reranker
    if reranker is None:
        loop = asyncio.get_event_loop()
        reranker = await loop.run_in_executor(executor, _load_reranker)
    return reranker


# -------------------- Security --------------------
def require_api_key(x_api_key: Optional[str] = Header(None)):
    """
    Enforce API key authentication when a key is configured.
    """
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return True

def get_auth_dep():
    """
    Produce either the API key dependency or a no-op depending on configuration.
    """
    return require_api_key if settings.api_key else (lambda: True)


# -------------------- Schemas --------------------
class RerankItem(BaseModel):
    """
    Candidate passage/document optionally carrying metadata.
    """
    text: str = Field(..., description="Passage/document to be scored")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadata returned as is in the output",
    )

class RerankRequest(BaseModel):
    """
    Payload for reranking:
    - query: the user query
    - items: candidate passages to score
    - top_k: optional cut-off for the number of returned results
    """
    query: str = Field(..., description="Request text")
    items: List[RerankItem] = Field(..., min_items=1, description="Candidates to score")
    top_k: Optional[int] = Field(
        default=None,
        description="Maximum number of returned passes",
    )
    return_scores: bool = True

class RerankedItem(BaseModel):
    """
    Single reranked item with original index preserved.
    """
    text: str
    score: float
    metadata: Optional[Dict[str, Any]] = None
    index: int  # original index in req.items

class RerankResponse(BaseModel):
    """
    Final response containing sorted results for a given query.
    """
    query: str
    model: str = settings.model_name
    results: List[RerankedItem]


# -------------------- FastAPI App --------------------
app = FastAPI(title="bge-reranker-v2-m3", version="1.0.0")

@app.on_event("startup")
async def startup():
    """
    Preload the model and run a small warmup to reduce the first-request latency.
    """
    m = await get_reranker()
    try:
        # Quick warmup using a minimal example.
        _ = m.compute_score(["warmup query", "warmup passage"])
        print(f"[---bge-reranker---] Warmup completed. Device = {device}")
    except Exception as e:
        print(f"[---bge-reranker---] Warmup failed (non-critical): {e}")

@app.get("/healthz")
async def healthz():
    """
    Basic health endpoint exposing model and runtime configuration.
    """
    return {
        "status": "ok",
        "model": settings.model_name,
        "device": device,
        "use_fp16": EFFECTIVE_FP16,
        "max_workers": settings.max_workers,
        "torch_num_threads": torch.get_num_threads(),
        "torch_num_interop_threads": torch.get_num_interop_threads()
        if hasattr(torch, "get_num_interop_threads")
        else None,
    }

@app.post("/", response_model=RerankResponse)
async def rerank(req: RerankRequest, _=Depends(get_auth_dep())):
    """
    Core reranking endpoint:
    - compute scores for (query, passage) pairs
    - sort results by score
    - optionally truncate with top_k
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="The list of items must not be empty.")

    m = await get_reranker()

    # Build list of [query, item.text] pairs expected by FlagReranker.
    pairs = [[req.query, it.text] for it in req.items]

    loop = asyncio.get_event_loop()
    try:
        scores: List[float] = await loop.run_in_executor(
            executor,
            lambda: m.compute_score(pairs),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rerank inference error: {e}")

    # Attach original index and metadata, then sort by score descending.
    indexed = [
        (i, it, float(score))
        for i, (it, score) in enumerate(zip(req.items, scores))
    ]
    indexed.sort(key=lambda x: x[2], reverse=True)

    if req.top_k is not None:
        indexed = indexed[: req.top_k]

    # Convert internal structure to response schema.
    results = [
        RerankedItem(
            text=it.text,
            score=score if req.return_scores else 0.0,
            metadata=it.metadata,
            index=i,
        )
        for (i, it, score) in indexed
    ]

    return RerankResponse(query=req.query, results=results)

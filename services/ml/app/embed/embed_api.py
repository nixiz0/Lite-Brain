import os, asyncio
import torch
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Literal, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from huggingface_hub import snapshot_download
from FlagEmbedding import BGEM3FlagModel
from .embed_config import (
    API_KEY,
    DEVICE,
    MAX_WORKERS,
    EMB_MODEL_NAME,
    MODEL_DIR,
    MODEL_REVISION,
    TORCH_NUM_THREADS,
    TORCH_NUM_INTEROP,
)

# Disable tokenizers parallelism warnings to avoid noisy logs.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


# -------------- Device Config --------------
def _select_device(device_str: str) -> str:
    """
    If it builds on CUDA and no GPU is detected, then it will remain on the CPU.
    """
    dev = device_str or "cpu"
    if dev.startswith("cuda") and not torch.cuda.is_available():
        print("[EMBED boot] CUDA requested but not available, falling back to CPU.")
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


# -------------- Settings / Configuration --------------
class Settings(BaseSettings):
    """
    Runtime configuration for the embedding service.
    Values are primarily sourced from embed_config.
    """
    api_key: str = API_KEY
    device: str = DEVICE
    max_workers: int = MAX_WORKERS
    model_name: str = EMB_MODEL_NAME
    model_dir: str = MODEL_DIR
    model_revision: str = MODEL_REVISION

settings = Settings()

# Ensure the local model directory exists.
os.makedirs(settings.model_dir, exist_ok=True)


# -------------- Model management (local snapshot + lazy loading) --------------
model: Optional[BGEM3FlagModel] = None

# Pool of worker threads that execute blocking model inference without blocking the event loop
executor = ThreadPoolExecutor(max_workers=settings.max_workers)

def _local_model_ready(path: str) -> bool:
    """
    Return True if the model appears to be present locally.

    Heuristic: directory exists, contains a config.json and at least one
    weights file (*.safetensors or *.bin).
    """
    if not os.path.isdir(path):
        return False
    entries = set(os.listdir(path))
    has_config = "config.json" in entries
    has_weights = any(fn.endswith((".safetensors", ".bin")) for fn in entries)
    return has_config and has_weights

def _ensure_local_model() -> str:
    """
    Ensure a local copy of the model is available in model_dir.
    - If a valid model snapshot is already present in model_dir, reuse it.
    - Otherwise download it from the Hugging Face Hub using snapshot_download.
    """
    local_dir = settings.model_dir
    os.makedirs(local_dir, exist_ok=True)

    if _local_model_ready(local_dir):
        # Model already present locally.
        return local_dir

    # Model missing -> download a filtered snapshot to local_dir.
    print(f"[bge-m3] Model download {settings.model_name} in {local_dir} ...")
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
    print(f"[bge-m3] Download complete. Model available in {local_dir}.")
    return local_dir

def _load_model() -> BGEM3FlagModel:
    """
    Load BGEM3FlagModel from the local path, configuring device and FP16.
    - Forces the device to the configured value (cpu, cuda:0, etc.).
    - Enables FP16 only when running on a CUDA device.
    - Enables dense embedding normalization by default.
    """
    local_path = _ensure_local_model()

    kwargs = {
        "use_fp16": EFFECTIVE_FP16,
        "normalize_embeddings": True,  # always normalize dense embeddings
        "device": device,              # e.g. "cpu" or "cuda:0"
    }

    print(
        f"[bge-m3] Loading the model from {local_path} "
        f"(device={device}, fp16={EFFECTIVE_FP16})..."
    )
    m = BGEM3FlagModel(local_path, **kwargs)
    print("[bge-m3] Model loaded.")
    return m

async def get_model() -> BGEM3FlagModel:
    """
    Return the global model instance, loading it once in a background thread.

    This function is safe to call concurrently; the first caller triggers
    the heavy load, subsequent callers reuse the same global model.
    """
    global model
    if model is None:
        loop = asyncio.get_event_loop()
        model = await loop.run_in_executor(executor, _load_model)
    return model


# -------------- Security (optional API key) --------------
def require_api_key(x_api_key: Optional[str] = Header(None)):
    """
    FastAPI dependency that enforces an API key if one is configured.
    - If settings.api_key is set, the caller must provide a matching X-API-Key
      header (x_api_key here).
    - If no API key is configured, this dependency becomes a no-op.
    """
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return True

def get_auth_dep():
    """
    Return the appropriate authentication dependency.
    - If an API key is configured, return the require_api_key dependency.
    - Otherwise return a dummy lambda that always succeeds.
    """
    return require_api_key if settings.api_key else (lambda: True)


# -------------- Pydantic schemas --------------
class EmbedOptions(BaseModel):
    """
    Per-request options controlling embedding outputs and encoding behavior.
    """
    return_dense: bool = True       # Always active (by default)
    return_sparse: bool = False     # For Hybrid search (like BM25 type)
    return_colbert: bool = False    # For Need for extreme precision

    # Dense normalization is handled inside the model; kept for compatibility / debugging.
    normalize_dense: bool = True

    batch_size: int = 12
    max_length: int = 1024  # Default max_length is 1024; users can increase if needed.
    sparse_format: Literal["dict", "coo"] = "coo"

class EmbedRequest(BaseModel):
    """
    Input payload for the embedding endpoint.
    """
    texts: List[str] = Field(
        min_items=1,
        description="One or more strings to vectorize",
    )
    options: EmbedOptions = EmbedOptions()

class DenseEmbeddings(BaseModel):
    """
    Dense embeddings for each input text.
    """
    vectors: List[List[float]]

class SparseEntry(BaseModel):
    """
    Sparse representation for a single input text.

    ids: token/feature indices
    weights: corresponding scores/weights
    """
    ids: List[int]
    weights: List[float]

class ColBERTEmbeddings(BaseModel):
    """
    ColBERT-style token-level embeddings.

    vectors: per-text matrices of shape (num_tokens, 1024).
    """
    vectors: List[List[List[float]]]

class EmbedResponse(BaseModel):
    """
    Unified response type for all supported embedding outputs.
    """
    dense: Optional[DenseEmbeddings] = None
    sparse: Optional[List[SparseEntry]] = None
    colbert: Optional[ColBERTEmbeddings] = None
    model: str = settings.model_name
    dim: int = 1024
    # Maximum capacity of the underlying model; may be higher than the per-request max_length.
    max_length: int = 8192


# -------------- FastAPI application --------------
app = FastAPI(title="bge-m3-embeddings", version="1.0.0")

@app.on_event("startup")
async def startup():
    """
    Application startup hook.

    Pre-loads the model and runs a small warmup inference to reduce latency
    on the first real request. Warmup failures are logged but non-blocking.
    """
    m = await get_model()
    try:
        # Lightweight warmup: single short sentence, batch_size=1.
        m.encode(
            ["warmup test"],
            batch_size=1,
            max_length=32,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        print(f"[---bge-m3---] Inference warmup completed. Device = {device}")
    except Exception as e:
        print(f"[---bge-m3---] Warmup failed (non-blocking) : {e}")

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

@app.post("/", response_model=EmbedResponse)
async def embed(req: EmbedRequest, _=Depends(get_auth_dep())):
    """
    Main embedding endpoint.
    - Validates that at least one output type is requested.
    - Runs model.encode in a background thread.
    - Adapts the raw model output into the EmbedResponse schema.
    """
    if not (
        req.options.return_dense
        or req.options.return_sparse
        or req.options.return_colbert
    ):
        raise HTTPException(
            status_code=400,
            detail="Activate at least one output type (dense/sparse/colbert).",
        )

    m = await get_model()

    encode_kwargs = dict(
        batch_size=req.options.batch_size,
        max_length=req.options.max_length,
        return_dense=req.options.return_dense,
        return_sparse=req.options.return_sparse,
        return_colbert_vecs=req.options.return_colbert,
    )

    loop = asyncio.get_event_loop()
    try:
        # Run heavy encoding work in a thread pool to avoid blocking the event loop.
        out: Dict[str, Any] = await loop.run_in_executor(
            executor,
            lambda: m.encode(req.texts, **encode_kwargs),
        )
    except Exception as e:
        # Wrap any encoding-related failure as a 500 for the client.
        raise HTTPException(status_code=500, detail=f"Inference error: {e}")

    resp = EmbedResponse()

    # Dense embeddings
    if req.options.return_dense and "dense_vecs" in out:
        resp.dense = DenseEmbeddings(
            vectors=[list(map(float, v)) for v in out["dense_vecs"]]
        )

    # Sparse embeddings
    if req.options.return_sparse and "lexical_weights" in out:
        sparse_list: List[SparseEntry] = []
        for d in out["lexical_weights"]:
            if req.options.sparse_format == "dict":
                # Keep original key ordering by iterating over the dict keys directly.
                ids = list(map(int, d.keys()))
                weights = [float(d[k]) for k in ids]
            else:
                # COO-like format: sort by id to provide a deterministic ordering.
                items = sorted(
                    ((int(k), float(v)) for k, v in d.items()),
                    key=lambda x: x[0],
                )
                ids = [i for i, _ in items]
                weights = [w for _, w in items]
            sparse_list.append(SparseEntry(ids=ids, weights=weights))
        resp.sparse = sparse_list

    # ColBERT embeddings
    if req.options.return_colbert and "colbert_vecs" in out:
        colbert_vectors: List[List[List[float]]] = []
        for mat in out["colbert_vecs"]:
            colbert_vectors.append(
                [list(map(float, row)) for row in mat]
            )
        resp.colbert = ColBERTEmbeddings(vectors=colbert_vectors)

    return resp

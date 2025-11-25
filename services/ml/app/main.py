from fastapi import FastAPI
from .embed.embed_api import app as embed_app, startup as embed_startup
from .rerank.rerank_api import app as rerank_app, startup as rerank_startup
from .ocr.ocr_api import app as ocr_app, startup as ocr_startup


# Root FastAPI application.
app = FastAPI(
    title="Unified API with Embeddings + Rerank API + OCR",
    version="1.0.0",
)

# ========== [API ENDPOINTS] ==========
@app.on_event("startup")
async def unified_startup():
    """
    Global startup hook.

    Pre-warms the embeddings, reranker, ocr models so that the first requests
    to the /embed /rerank /ocr sub-apps have lower latency.
    """
    print("[unified] Startup: warming up APIs systems...")
    try:
        # Delegate Embeddings warmup to embed_api's existing startup routine.
        await embed_startup()
    except Exception as e:
        print(f"[unified] Embeddings warmup failed (non-fatal): {e}")

    try:
        # Pre-warm Reranker model if a startup routine is defined in rerank_api.
        await rerank_startup()
    except Exception as e:
        print(f"[unified] Reranker warmup failed (non-fatal): {e}")

    try:
        # Pre-warm OCR model if a startup routine is defined in ocr_api.
        await ocr_startup()
    except Exception as e:
        print(f"[unified] OCR warmup failed (non-fatal): {e}")

@app.get("/")
def root():
    """
    Basic service discovery endpoint for the unified API.
    Returns available sub-services and their main routes.
    """
    return {
        "message": "Unified Embeddings + Rerank + OCR API is running",
        "services": {
            "embeddings": {
                "health": "/embed/healthz",
                "embed": "/embed",
            },
            "rerank": {
                "health": "/rerank/healthz",
                "rerank": "/rerank",
            },
            "ocr": {
                "health": "/ocr/healthz",
                "extract": "/ocr",
            },
        },
    }

@app.get("/healthz")
def healthz():
    """
    Shallow health check for the unified API.
    Doesn't probe sub-services deeply; they expose their own health endpoints.
    """
    return {
        "status": "ok",
        "services": ["embeddings", "rerank", "ocr"],
    }


# ========== [API ENDPOINTS MOUNTING] ==========
# Mount sub-applications under their respective prefixes.
# Each sub-app defines its own routes and internal configuration.
app.mount("/embed", embed_app)
app.mount("/rerank", rerank_app)
app.mount("/ocr", ocr_app)

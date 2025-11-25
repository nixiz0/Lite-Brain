import httpx, json
from typing import Literal, Optional, Set

from CONFIG import OLLAMA_URL, REQUIRED_LLM_MODELS
from i18n import t


# =========== Ollama Endpoints ===========
OLLAMA_TAGS_URL = OLLAMA_URL.rstrip("/") + "/api/tags"
OLLAMA_PULL_URL = OLLAMA_URL.rstrip("/") + "/api/pull"


# =========== Bootstrap State ===========
class BootstrapState:
    """
    In-memory state container for the model bootstrap process.
    This is meant to be read by the API (e.g. a status endpoint) to
    expose progress to the UI.
    """

    def __init__(self) -> None:
        # Global lifecycle of the bootstrap
        self.status: Literal["idle", "checking", "downloading", "ready", "error"] = "idle"
        # Name of the model currently being downloaded (if any)
        self.current_model: Optional[str] = None
        # Download progress in percent (0.0–100.0)
        self.progress: float = 0.0
        # Human-readable message to show in the UI
        self.message: str = ""
        # Set of required models that are missing locally
        self.missing: Set[str] = set()

    def to_dict(self):
        """
        Serializes the state in a JSON-friendly format.
        """
        return {
            "status": self.status,
            "current_model": self.current_model,
            "progress": self.progress,
            "message": self.message,
            "missing": list(self.missing),
        }


# Single global state instance shared by bootstrap + status endpoint
state = BootstrapState()


# =========== Helper Functions ===========
async def _get_installed_models() -> Set[str]:
    """
    Queries Ollama /api/tags to retrieve the list of installed models.

    Expected response format:
        {
          "models": [
            {"name": "qwen3:4b", ...},
            ...
          ]
        }

    Returns a set of model names.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(OLLAMA_TAGS_URL)
        r.raise_for_status()
        data = r.json()
        return {m["name"] for m in data.get("models", [])}


async def _pull_model(name: str):
    """
    Downloads a single model via Ollama /api/pull, streaming progress
    and updating the global BootstrapState as lines arrive.
    """
    state.status = "downloading"
    state.current_model = name
    state.progress = 0.0
    state.message = t("bootstrap_downloading_model").format(name=name)

    async with httpx.AsyncClient(timeout=None) as client:
        # /api/pull returns a stream of JSON lines describing progress
        async with client.stream("POST", OLLAMA_PULL_URL, json={"name": name}) as r:
            async for line in r.aiter_lines():
                if not line:
                    continue

                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    # Ignore malformed lines instead of failing the download
                    continue

                status = evt.get("status")     # e.g. "downloading", "verifying", "success"
                completed = evt.get("completed")
                total = evt.get("total")

                if status:
                    state.message = t("bootstrap_model_status").format(
                        name=name,
                        status=status,
                    )

                # Update percentage if total is known
                if completed is not None and total:
                    state.progress = round(100.0 * completed / total, 1)

    # Ensure final state is marked as 100% for the model
    state.progress = 100.0
    state.message = t("bootstrap_model_done").format(name=name)


# =========== Public API ===========
async def ensure_models_ready():
    """
    Bootstrap function to call at FastAPI startup.

    Responsibilities:
    - Check which required models are already installed
    - Download missing models sequentially
    - Keep global BootstrapState updated for UI polling
    """
    # Short-circuit if no models are configured as required
    if not REQUIRED_LLM_MODELS:
        state.status = "ready"
        state.message = t("bootstrap_no_models_required")
        return

    state.status = "checking"
    state.message = t("bootstrap_checking_models")

    # Query Ollama for installed models
    try:
        installed = await _get_installed_models()
    except Exception as e:
        state.status = "error"
        state.message = t("bootstrap_contact_error").format(error=str(e))
        return

    # Compute missing models in required order
    missing = [m for m in REQUIRED_LLM_MODELS if m not in installed]
    state.missing = set(missing)

    # If everything is already installed, mark as ready
    if not missing:
        state.status = "ready"
        state.message = t("bootstrap_all_installed")
        state.progress = 100.0
        return

    # Sequentially pull missing models; abort on first failure
    for model in missing:
        try:
            await _pull_model(model)
        except Exception as e:
            state.status = "error"
            state.message = t("bootstrap_pull_error").format(
                model=model,
                error=str(e),
            )
            return

    # All models downloaded successfully
    state.status = "ready"
    state.current_model = None
    state.message = t("bootstrap_all_downloaded")
    state.progress = 100.0


def get_bootstrap_state():
    """
    Returns the current bootstrap state as a dict,
    ready to be used in an API response.
    """
    return state.to_dict()

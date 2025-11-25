import requests
from CONFIG import EMBED_API_URL, EMBED_API_TIMEOUT_S


# =========== Helper Functions ===========
def _build_headers():
    """
    Builds optional API headers (e.g., API key) if available in globals().
    Here normally don't have any API KEY but for good practice.
    """
    headers = {}
    api_key = globals().get("EMBED_API_KEY") or globals().get("API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


# =========== Call API Embedding Function ===========
def get_embeddings(texts, timeout=EMBED_API_TIMEOUT_S):
    """
    Calls the embedding API and returns dense vector embeddings.

    Args:
        texts (str | list[str]): Single text or list of texts to embed.
        timeout (int): HTTP timeout in seconds.

    Returns:
        list[float] or list[list[float]]: One vector or a list of vectors.
    """

    # Normalize input to a list while tracking whether it was a single string
    if isinstance(texts, str):
        texts_list = [texts]
        is_single = True
    else:
        texts_list = list(texts)
        if not texts_list:
            raise ValueError("The 'texts' list cannot be empty.")
        is_single = False

    # Embedding API call payload (defaults used by the server)
    payload = {
        "texts": texts_list,
    }

    resp = requests.post(
        EMBED_API_URL,
        json=payload,
        headers=_build_headers(),
        timeout=timeout,
    )

    if not resp.ok:
        raise Exception(f"Embedding API error {resp.status_code}: {resp.text}")

    data = resp.json()

    if "dense" not in data or data["dense"] is None:
        raise Exception(f"Invalid API response (missing dense vectors): {data}")

    vectors = data["dense"]["vectors"]

    # Return a single vector if input was a single string
    return vectors[0] if is_single else vectors

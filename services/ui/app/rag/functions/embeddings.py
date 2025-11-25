import requests
from typing import List, Dict, Any, Tuple, Optional
from CONFIG import EMBED_API_URL, EMBED_API_TIMEOUT_S


def embed_query(text: str) -> Tuple[List[float], Optional[Dict[str, Any]]]:
    """
    Calls the embedding API to encode the query.
    Returns (dense_vector, sparse_dict). Sparse output is preserved for future use.
    """
    payload = {
        "texts": [text],
        "options": {
            "return_dense": True,
            "return_sparse": True,
            "return_colbert": False,
            "sparse_format": "coo",
        },
    }

    resp = requests.post(
        EMBED_API_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=EMBED_API_TIMEOUT_S,
    )
    resp.raise_for_status()
    data = resp.json()

    dense_vec = data["dense"]["vectors"][0]
    sparse_entry = data.get("sparse")
    sparse = sparse_entry[0] if sparse_entry else None
    return dense_vec, sparse

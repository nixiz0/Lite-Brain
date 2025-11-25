import requests
from typing import List, Dict, Any
from CONFIG import RERANKING_API_URL, RERANKING_API_TIMEOUT_S


def rerank_passages(
    query: str,
    passages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Uses BGE reranker API to rerank retrieved passages.
    Expects passages with at least {"text": str}.
    Returns a list sorted by descending model score.
    """
    if not passages:
        return []

    items = [{"text": p["text"], "metadata": p.get("metadata", {})} for p in passages]

    payload = {
        "query": query,
        "items": items,
        "top_k": len(items),
        "return_scores": True,
    }

    resp = requests.post(
        RERANKING_API_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=RERANKING_API_TIMEOUT_S,
    )
    resp.raise_for_status()
    data = resp.json()

    # Build new passage list with reranker scores
    reranked: List[Dict[str, Any]] = []
    for r in data.get("results", []):
        idx = r.get("index")
        if idx is None or not (0 <= idx < len(passages)):
            continue
        p = passages[idx].copy()
        p["score_rerank"] = r.get("score", 0.0)
        reranked.append(p)

    # Fallback: no index returned → use model output directly
    if not reranked and data.get("results"):
        for r in data["results"]:
            reranked.append(
                {
                    "text": r.get("text", ""),
                    "score_rerank": r.get("score", 0.0),
                    "metadata": r.get("metadata", {}),
                }
            )

    reranked.sort(key=lambda x: x.get("score_rerank", 0.0), reverse=True)
    return reranked

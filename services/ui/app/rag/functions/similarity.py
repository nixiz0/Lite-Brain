from math import sqrt
from typing import List


# =========== Classic Cosine Function ===========
def cosine(a: List[float], b: List[float]) -> float:
    """Computes cosine similarity between two dense vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = sqrt(sum(x * x for x in a))
    nb = sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# =========== MMR Similarity Function ===========
def mmr_similarity(
    query_vec: List[float],
    doc_vecs: List[List[float]],
    top_k: int,
    lambda_mult: float = 0.5,
) -> List[int]:
    """
    Maximal Marginal Relevance (MMR).
    Selects doc indices maximizing relevance to query while maintaining diversity.
    Returns selected indices in ranking order.
    """
    if not doc_vecs:
        return []

    top_k = min(top_k, len(doc_vecs))
    selected: List[int] = []
    candidate_indices = list(range(len(doc_vecs)))

    while candidate_indices and len(selected) < top_k:
        best_idx = None
        best_score = -1e9

        # Evaluate each remaining candidate
        for idx in candidate_indices:
            sim_to_query = cosine(query_vec, doc_vecs[idx])
            # Max similarity with already selected docs = diversity penalty
            diversity_penalty = (
                max(cosine(doc_vecs[idx], doc_vecs[j]) for j in selected)
                if selected else 0.0
            )
            score = lambda_mult * sim_to_query - (1 - lambda_mult) * diversity_penalty

            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None:
            break

        selected.append(best_idx)
        candidate_indices.remove(best_idx)

    return selected

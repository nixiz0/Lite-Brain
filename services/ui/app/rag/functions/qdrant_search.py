from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchAny,
    SearchParams,
    ScoredPoint,
)
from CONFIG import QDRANT_URL


qdrant = QdrantClient(url=QDRANT_URL)

def build_filter_for_documents(document_ids: List[int]) -> Optional[Filter]:
    """
    Builds a Qdrant filter restricting search to specific document_ids.
    Note: document_id is stored as string in payload.
    """
    if not document_ids:
        return None

    return Filter(
        must=[
            FieldCondition(
                key="document_id",
                match=MatchAny(any=[str(did) for did in document_ids]),
            )
        ]
    )

def search_in_collection(
    collection_name: str,
    query_dense: List[float],
    query_sparse: Optional[Dict[str, Any]],
    q_filter: Optional[Filter],
    limit: int,
) -> List[Any]:
    """
    Dense vector search in a Qdrant collection.
    query_sparse is ignored to remain compatible with the current Qdrant setup.
    """
    search_params = SearchParams(hnsw_ef=128)

    results = qdrant.search(
        collection_name=collection_name,
        query_vector=query_dense,
        query_filter=q_filter,
        limit=limit,
        with_payload=True,
        with_vectors=True,  # needed for MMR or later Rocchio refinement
        search_params=search_params,
    )

    return results


def scroll_in_collection(
    collection_name: str,
    q_filter: Optional[Filter] = None,
    limit_per_page: int = 256,
) -> List[ScoredPoint]:
    """
    Fetch all points from a Qdrant collection using scroll pagination.

    Args:
        collection_name: Name of the Qdrant collection.
        q_filter: Optional Qdrant filter to restrict results.
        limit_per_page: Max number of points requested per scroll call.

    Returns:
        A flat list of all ScoredPoint objects matching the filter.
    """
    all_points: List[ScoredPoint] = []
    offset = None

    # Keep scrolling until Qdrant signals there are no more points
    while True:
        points, next_offset = qdrant.scroll(
            collection_name=collection_name,
            scroll_filter=q_filter,
            with_payload=True,
            with_vectors=True,
            limit=limit_per_page,
            offset=offset,
        )

        # Accumulate points from the current page
        all_points.extend(points)

        # When next_offset is None, we've reached the end of the collection
        if next_offset is None:
            break

        # Continue from the last offset
        offset = next_offset

    return all_points

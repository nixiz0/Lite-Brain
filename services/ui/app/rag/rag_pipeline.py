from typing import List, Dict, Any, Tuple, Optional
from qdrant_client.models import (
    Filter,
)

from CONFIG import (
    TOP_K_HYBRID,
    TOP_K_MMR,
    TOP_K_RERANK,
    MMR_LAMBDA,
    MAX_FULL_DOC_CHUNKS,
)
from .functions.similarity import mmr_similarity
from .functions.embeddings import embed_query
from .functions.rerank import rerank_passages
from .functions.qdrant_search import build_filter_for_documents, search_in_collection, scroll_in_collection


# =========== RAG Function ===========
def rag_retrieve(
    query: str,
    folder_ids: List[int],
    document_ids: List[int],
) -> List[Dict[str, Any]]:
    """
    RAG retrieval pipeline:
      1) Embed query
      2) Dense search in relevant Qdrant collections
      3) MMR for diversity
      4) Returns passages with metadata + vectors (not reranked)
    """
    # 1) Query embedding
    query_dense, query_sparse = embed_query(query)

    # 2) Determine which collections to search
    collections: List[Tuple[str, Optional[Filter]]] = []

    if folder_ids:
        doc_filter = build_filter_for_documents(document_ids) if document_ids else None
        for fid in folder_ids:
            collections.append((str(fid), doc_filter))
    else:
        # Querying docs without folders is unsupported without mapping logic
        if document_ids:
            raise RuntimeError(
                "rag_retrieve: 'document_ids' without 'folder_ids' requires "
                "mapping doc_id -> folder_id."
            )

    # 3) Dense search
    all_hits: List[Dict[str, Any]] = []

    for collection_name, q_filter in collections:
        res = search_in_collection(
            collection_name,
            query_dense=query_dense,
            query_sparse=query_sparse,
            q_filter=q_filter,
            limit=TOP_K_HYBRID,
        )

        for p in res:
            payload = p.payload or {}
            all_hits.append(
                {
                    "collection": collection_name,
                    "id": p.id,
                    "score": p.score,
                    "vector": p.vector,
                    "text": payload.get("text", ""),
                    "document_id": payload.get("document_id"),
                    "file_name": payload.get("file_name"),
                    "file_extension": payload.get("file_extension"),
                    "chunk_index": payload.get("chunk_index"),
                }
            )

    if not all_hits:
        return []

    # 4) MMR ranking
    doc_vecs = [h["vector"] for h in all_hits]
    mmr_indices = mmr_similarity(
        query_vec=query_dense,
        doc_vecs=doc_vecs,
        top_k=TOP_K_MMR,
        lambda_mult=MMR_LAMBDA,
    )

    return [all_hits[i] for i in mmr_indices]



# =========== RAG with Reranking Function ===========
def rag_with_rerank(
    query: str,
    folder_ids: List[int],
    document_ids: List[int],
) -> List[Dict[str, Any]]:
    """
    Full RAG pipeline:
      - Dense retrieval + MMR
      - BGE reranking
      - Returns top passages up to TOP_K_RERANK
    """
    candidates = rag_retrieve(query, folder_ids, document_ids)
    if not candidates:
        return []

    # Prepare passages for reranking
    rerank_ready = []
    for c in candidates:
        if not c["text"]:
            continue
        rerank_ready.append(
            {
                "text": c["text"],
                "metadata": {
                    "collection": c["collection"],
                    "id": c["id"],
                    "document_id": c["document_id"],
                    "file_name": c["file_name"],
                    "chunk_index": c["chunk_index"],
                },
                "_original": c,
            }
        )

    if not rerank_ready:
        return []

    # Rerank
    reranked = rerank_passages(query, rerank_ready)
    if not reranked:
        return []

    # Map reranked results back to original metadata
    final_results: List[Dict[str, Any]] = []
    for r in reranked[:TOP_K_RERANK]:
        if "_original" in r:
            orig = r["_original"]
            orig["score_rerank"] = r.get("score_rerank", 0.0)
            final_results.append(orig)
        else:
            final_results.append(r)

    return final_results


# =========== RAG on all Documents ===========
def rag_full_document(
    folder_ids: List[int],
    document_ids: List[int],
    max_chunks: int = MAX_FULL_DOC_CHUNKS,
) -> List[Dict[str, Any]]:
    """
    'Full document' mode:
      - doesn't depend on the user query
      - retrieves all chunks for the selected documents
      - returns them sorted by (document_id, chunk_index)
    """
    # (collection_name, optional_filter) pairs for Qdrant collections
    collections: List[Tuple[str, Optional[Filter]]] = []

    if folder_ids:
        # If specific documents are provided, build a filter to restrict to them
        doc_filter = build_filter_for_documents(document_ids) if document_ids else None
        for fid in folder_ids:
            # Each folder_id corresponds to a Qdrant collection
            collections.append((str(fid), doc_filter))
    else:
        # Without folder_ids we cannot know which collection a document_id belongs to
        if document_ids:
            raise RuntimeError(
                "rag_full_document: 'document_ids' without 'folder_ids' "
                "requires mapping doc_id -> folder_id."
            )

    all_hits: List[Dict[str, Any]] = []

    for collection_name, q_filter in collections:
        # Ideally use Qdrant scroll here to fetch all points matching the filter
        points = scroll_in_collection(
            collection_name=collection_name,
            q_filter=q_filter,
        )

        for p in points:
            payload = p.payload or {}
            # Normalize Qdrant point into a generic hit structure
            all_hits.append(
                {
                    "collection": collection_name,
                    "id": p.id,
                    "text": payload.get("text", ""),
                    "vector": p.vector,
                    "document_id": payload.get("document_id"),
                    "file_name": payload.get("file_name"),
                    "file_extension": payload.get("file_extension"),
                    "chunk_index": payload.get("chunk_index") or 0,
                }
            )

    if not all_hits:
        return []

    # Ensure deterministic order: chunks strictly sorted by document then chunk index
    all_hits.sort(key=lambda h: (int(h["document_id"]), int(h["chunk_index"])))

    # Optionally cap the number of returned chunks
    if max_chunks and len(all_hits) > max_chunks:
        all_hits = all_hits[:max_chunks]

    return all_hits



# =========== Formatting Markdown from retrieved passages ===========
def build_context_markdown(passages: List[Dict[str, Any]]) -> str:
    """
    Builds a Markdown context block from retrieved passages for LLM consumption.
    """
    if not passages:
        return ""

    blocks = []
    for i, p in enumerate(passages, start=1):
        header = f"### Extract {i}"

        meta_parts = []
        if p.get("file_name"):
            meta_parts.append(f"File : {p['file_name']}")
        if p.get("document_id") is not None:
            meta_parts.append(f"Doc ID : {p['document_id']}")
        if p.get("chunk_index") is not None:
            meta_parts.append(f"Chunk : {p['chunk_index']}")

        if meta_parts:
            header += f" ({' • '.join(meta_parts)})"

        text = (p.get("text") or "").strip()
        blocks.append(f"{header}\n\n{text}")

    return "\n\n---\n\n".join(blocks)

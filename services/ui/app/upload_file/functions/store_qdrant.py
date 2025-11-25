import uuid
from qdrant_client.http import models


def store_in_qdrant(qdrant, collection, vectors, metadatas, texts):
    """
    Store vectors, metadata, and texts in a Qdrant collection.

    - Creates the collection if it doesn't exist.
    - Each text chunk is stored as a unique point with metadata.

    Args:
        qdrant: Qdrant client instance.
        collection: Name of the collection (str or convertible to str).
        vectors: List of vector embeddings.
        metadatas: List of metadata dicts for each vector.
        texts: List of text chunks.
    """
    collection_name = str(collection)

    # Create collection if it doesn't exist
    try:
        qdrant.get_collection(collection_name=collection_name)
    except Exception:
        # Assumes all vectors have same length
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=len(vectors[0]),
                distance="Cosine"
            )
        )

    points = []
    for i, (vector, metadata, text) in enumerate(zip(vectors, metadatas, texts)):
        # Keep only important metadata keys
        filtered_metadata = {k: v for k, v in metadata.items()
                             if k in ("document_id", "file_name", "file_extension")}
        filtered_metadata["chunk_index"] = i  # Index of chunk in the document

        # Generate a unique UUID for each chunk
        point_id = str(uuid.uuid4())

        # Prepare point structure for Qdrant
        points.append(
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload={**filtered_metadata, "text": text}
            )
        )

    # Upsert all points in the collection
    qdrant.upsert(
        collection_name=collection_name,
        points=points
    )

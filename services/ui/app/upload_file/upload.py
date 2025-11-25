import traceback
from pathlib import Path
from typing import Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PDFPlumberLoader,
    Docx2txtLoader,
    JSONLoader,
    UnstructuredMarkdownLoader,
)
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_community.document_loaders.excel import UnstructuredExcelLoader
from qdrant_client import QdrantClient

from CONFIG import QDRANT_URL, CHUNK_SIZE, OVERLAP
from app.upload_file.functions.loader import get_loader
from app.upload_file.functions.embeddings import get_embeddings
from app.upload_file.functions.store_qdrant import store_in_qdrant
from app.upload_file.functions.ocr import analyze_pdf_need_ocr, ocr_pages, ocr_api
from app.upload_file.functions.extract_pptx import extract_pptx_pages


# =========== Initialization ===========
# Supported formats are:
# png - jpg - jpeg - pdf - docx
# json - md - csv - xlsx - pptx
IMAGE_FILE_TYPES = ["png", "jpg", "jpeg"]
SUPPORTED_FILE_TYPES = {
    "pdf": PDFPlumberLoader,
    "docx": Docx2txtLoader,
    "json": JSONLoader,
    "md": UnstructuredMarkdownLoader,
    "csv": CSVLoader,
    "xlsx": UnstructuredExcelLoader,
}

# Qdrant client instance (reused across calls)
qdrant = QdrantClient(url=QDRANT_URL)

class UploadProcessingError(Exception):
    """Domain-level exception for document processing failures."""


# =========== Upload File Final Function ===========
def process_uploaded_file(
    file_path: str | Path,
    *,
    folder_name: Optional[str],
    folder_id: Optional[str],
    user_id: Optional[str],
    document_id: Optional[str],
    file_name: Optional[str] = None,
    file_extension: Optional[str] = None,
) -> dict:
    """
    Main processing pipeline for an uploaded file.
    Steps:
      - Load / OCR / extract text depending on type
      - Normalize and aggregate page text
      - Chunk text for embeddings
      - Vectorize chunks
      - Store vectors + metadata in Qdrant

    Raises UploadProcessingError for any functional failure.
    """

    file_path = Path(file_path)
    if not file_path.exists():
        raise UploadProcessingError(f"File not found: {file_path}")

    try:
        file_name_val = file_name or file_path.name
        file_ext = (file_extension or file_path.suffix.lstrip(".")).lower()

        # ---- Image: direct OCR ----
        if file_ext in IMAGE_FILE_TYPES:
            try:
                # Full page OCR via external OCR API
                ocr_text = ocr_api(str(file_path))
                page_content = (ocr_text or "").strip()
            except Exception as e:
                traceback.print_exc()
                raise UploadProcessingError(f"OCR failed for image: {e}") from e

        # ---- PDF: analyze then optionally OCR low-quality pages ----
        elif file_ext == "pdf":
            loader = get_loader(file_ext, str(file_path), SUPPORTED_FILE_TYPES)
            if not loader:
                raise UploadProcessingError("Unsupported file type (PDF loader missing)")

            try:
                # Each returned doc corresponds to a page or content block
                docs = loader.load()
                # Ensure pages are sorted by page index when available
                if hasattr(docs[0], "metadata") and "page" in docs[0].metadata:
                    pages = sorted(docs, key=lambda d: d.metadata["page"])
                    pages_text = [d.page_content for d in pages]
                else:
                    pages_text = [d.page_content for d in docs]
            except Exception as e:
                traceback.print_exc()
                raise UploadProcessingError(f"Failed to load PDF: {e}") from e

            # Detect whether OCR is needed based on page quality
            (
                needs_ocr,
                total_pages,
                blank_pages,
                total_chars,
                avg_chars_per_page,
            ) = analyze_pdf_need_ocr(pages_text)

            if needs_ocr:
                # Selective OCR only on low-quality pages
                chunks_meta = ocr_pages(pages_text, str(file_path))
            else:
                # Use native extracted text directly
                chunks_meta = [
                    {
                        "text": (t or "").strip(),
                        "source": "native",
                        "page_number": i + 1,
                    }
                    for i, t in enumerate(pages_text)
                    if (t or "").strip()
                ]
            page_content = "\n\n".join(c["text"] for c in chunks_meta)

        # ---- PPTX: extract slide-by-slide text ----
        elif file_ext == "pptx":
            try:
                pages = extract_pptx_pages(str(file_path))
            except Exception as e:
                traceback.print_exc()
                raise UploadProcessingError(f"Failed to load PPTX: {e}") from e

            # Filter out empty slides
            pages = [p for p in pages if (p["text"] or "").strip()]
            if not pages:
                raise UploadProcessingError("No text extracted from PPTX")

            # Merge slides in order for embeddings
            page_content = "\n\n".join(p["text"] for p in pages)

        # ---- TXT: simple file read with encoding fallback ----
        elif file_ext == "txt":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    page_content = f.read().strip()
            except UnicodeDecodeError:
                # Fallback if file wasn't UTF-8
                with open(file_path, "r", encoding="latin-1") as f:
                    page_content = f.read().strip()

        # ---- Other supported formats using generic loaders ----
        elif file_ext in SUPPORTED_FILE_TYPES:
            loader = get_loader(file_ext, str(file_path), SUPPORTED_FILE_TYPES)
            if not loader:
                raise UploadProcessingError("Unsupported file type (loader missing)")

            try:
                docs = loader.load()
                full_text = "\n".join(d.page_content for d in docs)
            except Exception as e:
                traceback.print_exc()
                raise UploadProcessingError(f"Failed to load file: {e}") from e
            page_content = full_text.strip()

        # ---- Unsupported extension ----
        else:
            raise UploadProcessingError(f"Unsupported file extension: {file_ext}")

        if not page_content:
            raise UploadProcessingError("No text extracted from document")

        # ---- Split extracted text into overlapping chunks ----
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=OVERLAP,
        )
        chunks = splitter.split_text(page_content)
        if not chunks:
            raise UploadProcessingError("No chunks generated from document")

        # ---- Batch embedding call for all chunks ----
        try:
            embeddings = get_embeddings(chunks)
        except Exception as e:
            traceback.print_exc()
            raise UploadProcessingError(f"Embedding failed: {e}") from e

        # Attach consistent metadata to each chunk
        metadatas = [
            {
                "folder_id": folder_id,
                "folder_name": folder_name,
                "user_id": user_id,
                "document_id": document_id,
                "file_name": file_name_val,
                "file_extension": file_ext,
            }
            for _ in chunks
        ]

        # ---- Store vectors + metadata into Qdrant ----
        try:
            # Use folder ID as collection name
            collection_name = str(folder_id) if folder_id is not None else "default"
            store_in_qdrant(
                qdrant=qdrant,
                collection=collection_name,
                vectors=embeddings,
                metadatas=metadatas,
                texts=chunks,
            )
        except Exception as e:
            traceback.print_exc()
            raise UploadProcessingError(f"Failed to store in Qdrant: {e}") from e

        return {
            "status": f"Finished upload on: {folder_name}",
            "folder_id": folder_id,
            "user_id": user_id,
            "document_id": document_id,
            "file_name": file_name_val,
            "file_extension": file_ext,
        }

    except UploadProcessingError:
        # Expected business-level errors are re-raised unchanged
        raise
    except Exception as e:
        # Any unexpected error is wrapped into a domain-level exception
        traceback.print_exc()
        raise UploadProcessingError(f"Unhandled error: {e}") from e

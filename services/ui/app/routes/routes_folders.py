import re, unicodedata
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, Depends, Form, File
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session as OrmSession
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FilterSelector, FieldCondition, MatchValue

from CONFIG import QDRANT_URL, UPLOAD_ROOT
from app.web_templates import render_base
from i18n import t
from ..db import get_db
from ..models import Conversation, Folder, Document
from ..upload_file.upload import process_uploaded_file, UploadProcessingError
from .functions.parse_ids import parse_ids_csv


router = APIRouter()

# Qdrant client used for vector storage per folder (collection per folder_id)
qdrant = QdrantClient(url=QDRANT_URL)

# =========== Helper Functions ===========
def slugify(name: str, max_len: int = 60) -> str:
    """
    Normalize a folder/file name into a safe, ASCII-only slug.
    - Removes diacritics.
    - Replaces invalid chars with '-'.
    - Collapses multiple '-' into one.
    - Truncates to `max_len`.
    """
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", s).strip("-._")
    s = re.sub(r"-{2,}", "-", s)
    return s[:max_len] or t("slug_fallback_folder")

def folder_documents(folder: Folder, db: OrmSession) -> List[Document]:
    """
    Return all documents for a folder ordered by most recent first.
    """
    return (
        db.execute(
            select(Document)
            .where(Document.folder_id == folder.id)
            .order_by(Document.added_at.desc())
        )
        .scalars()
        .all()
    )

def folder_dir_for(folder: Folder) -> Path:
    """
    Compute the canonical directory path on disk for a given folder.
    """
    return UPLOAD_ROOT / f"{folder.id}_{slugify(folder.name)}"

def find_existing_folder_dir(folder_id: int) -> Optional[Path]:
    """
    Locate an existing directory for a folder on disk.
    Handles both legacy pattern "folder_{id}" and the new "{id}_slug" format.
    """
    if not UPLOAD_ROOT.exists():
        return None

    for p in UPLOAD_ROOT.iterdir():
        if p.is_dir() and (
            p.name == f"folder_{folder_id}" or p.name.startswith(f"{folder_id}_")
        ):
            return p
    return None

def ensure_folder_dir(folder: Folder) -> Path:
    """
    Ensure a folder directory exists on disk and return its path.
    Reuses existing directory if it can be found, otherwise creates it.
    """
    d = find_existing_folder_dir(folder.id)
    if d:
        return d

    d = folder_dir_for(folder)
    d.mkdir(parents=True, exist_ok=True)
    return d

def move_folder_dir_if_needed(folder: Folder) -> Optional[Path]:
    """
    Move/rename a folder's directory if the canonical path changed (e.g. rename).
    - If an old directory exists and differs from the new canonical one, move it.
    - Avoids collisions by appending an incrementing suffix.
    - Returns the final directory path, or None if no directory exists.
    """
    old_dir = find_existing_folder_dir(folder.id)
    new_dir = folder_dir_for(folder)

    if old_dir and old_dir != new_dir:
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        candidate = new_dir
        i = 2
        # Ensure we don't overwrite an existing directory
        while candidate.exists():
            candidate = new_dir.with_name(new_dir.name + f"_{i}")
            i += 1
        new_dir = candidate
        old_dir.rename(new_dir)
        return new_dir

    return old_dir or new_dir



# =======================================================
# ============== FOLDERS Routes Endpoints ===============
# =======================================================
#  ---------- UI/UX Routes Endpoints ----------
@router.get("/sidebar/folders", response_class=HTMLResponse)
async def folders_fragment(request: Request, db: OrmSession = Depends(get_db)):
    """
    Sidebar fragment: list folders with associated document counts.
    """
    folders = (
        db.query(Folder, func.count(Document.id).label("doc_count"))
        .outerjoin(Document, Document.folder_id == Folder.id)
        .group_by(Folder.id)
        .order_by(Folder.created_at.asc())
        .all()
    )
    return render_base(
        request,
        "folders/_folders.html",
        {"folders": folders},
    )


@router.get("/folders/{folder_id}/modal", response_class=HTMLResponse)
async def folder_modal(folder_id: int, request: Request, db: OrmSession = Depends(get_db)):
    """
    Modal displaying folder details and its documents.
    """
    folder = db.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail=t("error_folder_not_found"))

    documents = folder_documents(folder, db)
    ensure_folder_dir(folder)

    return render_base(
        request,
        "folders/_folder_modal.html",
        {"folder": folder, "documents": documents},
    )



# ---------- CRUD FOLDERS Routes Endpoints ----------
@router.post("/folders/new", response_class=HTMLResponse)
async def create_folder(request: Request, db: OrmSession = Depends(get_db)):
    """
    Create a new folder with a unique name: '???', '??? 2', etc.
    """
    base_name = t("new_folder_base_name")
    existing_names = {name for (name,) in db.execute(select(Folder.name)).all()}
    name = base_name
    i = 2

    while name in existing_names:
        name = f"{base_name} {i}"
        i += 1

    folder = Folder(name=name)
    db.add(folder)
    db.commit()
    db.refresh(folder)

    ensure_folder_dir(folder)
    documents = folder_documents(folder, db)

    # HTMX trigger to refresh folders in the sidebar
    headers = {"HX-Trigger": "refresh-folders"}
    return render_base(
        request,
        "folders/_folder_modal.html",
        {"folder": folder, "documents": documents},
        headers=headers,
    )


@router.post("/folders/{folder_id}/rename", response_class=HTMLResponse)
async def rename_folder(
    folder_id: int,
    request: Request,
    name: str = Form(...),
    db: OrmSession = Depends(get_db),
):
    """
    Rename a folder and update its directory path on disk if needed.
    Also updates document paths if the underlying folder directory was moved.
    """
    folder = db.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail=t("error_folder_not_found"))

    new_name = (name or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail=t("error_name_empty"))

    # Check uniqueness of the new name
    exists = db.execute(
        select(Folder).where(Folder.name == new_name, Folder.id != folder.id)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail=t("error_name_exists"))

    old_dir = find_existing_folder_dir(folder.id)
    folder.name = new_name
    db.commit()

    # Move folder directory and rewrite document paths when relevant
    new_dir = move_folder_dir_if_needed(folder)
    if new_dir:
        docs = (
            db.execute(select(Document).where(Document.folder_id == folder.id))
            .scalars()
            .all()
        )
        for doc in docs:
            try:
                p = Path(doc.path)
                if old_dir:
                    try:
                        rel = p.relative_to(old_dir)
                        doc.path = str((new_dir / rel).resolve())
                    except Exception:
                        # Path not under old_dir; leave as-is
                        pass
            except Exception:
                # Invalid path string; ignore
                pass
        db.commit()

    headers = {"HX-Trigger": "refresh-folders"}
    return HTMLResponse("", headers=headers)


@router.delete("/folders/{folder_id}", response_class=HTMLResponse)
async def delete_folder(folder_id: int, request: Request, db: OrmSession = Depends(get_db)):
    """
    Delete a folder, its documents, their files on disk, and the associated Qdrant collection.
    """
    folder = db.get(Folder, folder_id)
    if folder:
        docs = folder_documents(folder, db)

        # 1) Delete files on disk and document rows in DB
        for doc in docs:
            try:
                p = Path(doc.path)
                if p.exists():
                    p.unlink()
            except Exception:
                pass

            db.delete(doc)

        # 2) Delete the folder row
        db.delete(folder)
        db.commit()

        # 3) Delete the physical directory (and its children)
        folder_dir = find_existing_folder_dir(folder_id)
        if folder_dir and folder_dir.exists():
            try:
                for child in folder_dir.iterdir():
                    if child.is_file():
                        child.unlink()
                    elif child.is_dir():
                        for sub in child.iterdir():
                            if sub.is_file():
                                sub.unlink()
                        child.rmdir()
                folder_dir.rmdir()
            except Exception:
                # Best effort cleanup
                pass

        # 4) Remove associated Qdrant collection
        try:
            qdrant.delete_collection(str(folder_id))
        except Exception as e:
            print(f"[Qdrant] error deletion collection {folder_id}: {e}")

    headers = {"HX-Trigger": "refresh-folders"}
    return HTMLResponse("", headers=headers)



# =======================================================
# ============= DOCUMENTS Routes Endpoints ==============
# =======================================================

# ---------- CRUD DOCUMENTS ----------
@router.post("/folders/{folder_id}/documents/upload", response_class=HTMLResponse)
async def upload_document(
    folder_id: int,
    request: Request,
    files: List[UploadFile] = File(...),
    db: OrmSession = Depends(get_db),
):
    """
    Upload files into a folder, create Document rows, and trigger the processing pipeline.
    - Limits to 5 files per request.
    - Avoids filename collisions by appending a numeric suffix.
    """
    folder = db.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail=t("error_folder_not_found"))

    folder_dir = ensure_folder_dir(folder)

    # Max 5 files, filter out invalid entries (no filename)
    files = [f for f in files if f and f.filename][:5]

    for up in files:
        original_name = Path(up.filename).name

        # Avoid name collisions on disk
        target_path = folder_dir / original_name
        i = 1
        while target_path.exists():
            target_path = folder_dir / f"{target_path.stem}_{i}{target_path.suffix}"
            i += 1

        # Read uploaded content
        content = await up.read()

        # Persist file on disk
        with target_path.open("wb") as f:
            f.write(content)

        # Create Document row
        doc = Document(
            name=target_path.name,
            path=str(target_path),
            folder_id=folder.id,
        )
        db.add(doc)
        db.flush()  # get doc.id without committing yet

        # Run embedding / upload pipeline
        try:
            file_ext = target_path.suffix.lstrip(".").lower()
            process_uploaded_file(
                file_path=target_path,
                folder_name=folder.name,
                folder_id=str(folder.id),
                user_id="",  # to be wired once user management is added
                document_id=str(doc.id),
                file_name=target_path.name,
                file_extension=file_ext,
            )
        except UploadProcessingError as e:
            # Keep the upload UX smooth even if vectorization fails
            print(f"[upload-pipeline] error for doc {doc.id}: {e}")
        except Exception as e:
            print(f"[upload-pipeline] unexpected error for doc {doc.id}: {e}")

    db.commit()

    documents = folder_documents(folder, db)
    headers = {"HX-Trigger": "refresh-folders"}
    return render_base(
        request,
        "folders/_folder_documents_list.html",
        {"folder": folder, "documents": documents},
        headers=headers,
    )


@router.post("/folders/{folder_id}/import-conversation/{conv_id}", response_class=HTMLResponse)
async def import_conversation_to_folder(
    folder_id: int,
    conv_id: int,
    request: Request,
    db: OrmSession = Depends(get_db),
):
    """
    Export a conversation as a .txt file into the folder, then run the processing pipeline.
    The transcript is built chronologically with timestamps and role labels.
    """
    folder = db.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail=t("error_folder_not_found"))

    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail=t("error_conversation_not_found"))

    folder_dir = ensure_folder_dir(folder)

    # 1) Build conversation transcript
    messages = conv.messages or []
    lines: List[str] = []

    title = conv.title or f"{t('transcript_conversation_fallback_title')} {conv.id}"
    lines.append(f"{t('transcript_title_label')} : {title}")
    lines.append("")  # blank line

    for msg in messages:
        role = msg.get("role", "unknown")
        if role == "user":
            role_label = t("transcript_role_user")
        elif role == "assistant":
            role_label = t("transcript_role_assistant")
        else:
            role_label = role.capitalize()

        ts = msg.get("ts")
        ts_part = f"[{ts}] " if ts else ""

        content = (msg.get("content") or "").strip()
        if not content:
            continue

        lines.append(f"{ts_part}{role_label} :")
        lines.append(content)
        lines.append("")  # blank line between messages

    transcript = "\n".join(lines).strip()
    if not transcript:
        raise HTTPException(status_code=400, detail=t("error_empty_conversation_export"))

    # 2) Save transcript as .txt in folder
    base_name = slugify(title) or f"conversation-{conv.id}"
    if not base_name.lower().endswith(".txt"):
        base_name = base_name + ".txt"

    target_path = folder_dir / base_name
    i = 2
    while target_path.exists():
        target_path = folder_dir / f"{target_path.stem}_{i}{target_path.suffix}"
        i += 1

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    # 3) Create Document row
    doc = Document(
        name=target_path.name,
        path=str(target_path),
        folder_id=folder.id,
    )
    db.add(doc)
    db.commit()       # commit early to release locks
    db.refresh(doc)   # ensure doc.id is populated

    # 4) Run upload / embeddings / Qdrant pipeline
    try:
        process_uploaded_file(
            file_path=target_path,
            folder_name=folder.name,
            folder_id=str(folder.id),
            user_id="",  # "" because it's mono-user app but keep for good practices
            document_id=str(doc.id),
            file_name=target_path.name,
            file_extension="txt",
        )
    except UploadProcessingError as e:
        print(f"[upload-pipeline] conversation error {conv.id} -> doc {doc.id}: {e}")
    except Exception as e:
        print(
            f"[upload-pipeline] unexpected error for conversation {conv.id} -> doc {doc.id}: {e}"
        )

    db.commit()

    # 5) Return updated document list for the folder modal
    documents = folder_documents(folder, db)
    headers = {"HX-Trigger": "refresh-folders"}
    return render_base(
        request,
        "folders/_folder_documents_list.html",
        {"folder": folder, "documents": documents},
        headers=headers,
    )


@router.post("/documents/{doc_id}/rename", response_class=HTMLResponse)
async def rename_document(
    doc_id: int,
    request: Request,
    name: str = Form(...),
    db: OrmSession = Depends(get_db),
):
    """
    Rename a document (DB only, file path on disk is left unchanged).
    """
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=t("error_document_not_found"))

    new_name = (name or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail=t("error_name_empty"))

    doc.name = new_name
    db.commit()

    folder = db.get(Folder, doc.folder_id)
    if not folder:
        return HTMLResponse("")

    documents = folder_documents(folder, db)
    return render_base(
        request,
        "folders/_folder_documents_list.html",
        {"folder": folder, "documents": documents},
    )


@router.delete("/documents/{doc_id}", response_class=HTMLResponse)
async def delete_document(doc_id: int, request: Request, db: OrmSession = Depends(get_db)):
    """
    Delete a document, its file on disk, and its vectors/payload in Qdrant.
    """
    doc = db.get(Document, doc_id)
    if not doc:
        return HTMLResponse("")

    folder_id = doc.folder_id
    path = Path(doc.path)

    # 1) Delete vectors + payload in Qdrant for this document
    if folder_id is not None:
        try:
            qdrant.delete(
                collection_name=str(folder_id),
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="document_id",
                                match=MatchValue(value=str(doc_id)),
                            )
                        ]
                    )
                ),
                wait=True,
            )
        except Exception as e:
            print(f"[Qdrant] error deleting vectors doc {doc_id}: {e}")

    # 2) Delete file on disk
    try:
        if path.exists():
            path.unlink()
    except Exception:
        # Ignore FS errors
        pass

    # 3) Delete DB row
    db.delete(doc)
    db.commit()

    # 4) Return updated folder document list (if folder still exists)
    folder = db.get(Folder, folder_id) if folder_id is not None else None
    if not folder:
        return HTMLResponse("")

    documents = folder_documents(folder, db)
    headers = {"HX-Trigger": "refresh-folders"}
    return render_base(
        request,
        "folders/_folder_documents_list.html",
        {"folder": folder, "documents": documents},
        headers=headers,
    )


@router.get("/documents/{doc_id}/download")
async def download_document(doc_id: int, db: OrmSession = Depends(get_db)):
    """
    Download a document's file from disk.
    """
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=t("error_document_not_found"))

    file_path = Path(doc.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=t("error_file_not_found_on_server"))

    return FileResponse(file_path, filename=doc.name)



# =======================================================
# SELECT (for RAG) FOLDERS & DOCUMENTS Routes Endpoints
# =======================================================
@router.get("/modal/source-selector", response_class=HTMLResponse)
async def source_selector_modal(request: Request, db: OrmSession = Depends(get_db)):
    """
    Modal to select folders/documents used as RAG sources.
    Reuses the same folder + doc_count query as the sidebar.
    """
    folders = (
        db.query(Folder, func.count(Document.id).label("doc_count"))
        .outerjoin(Document, Document.folder_id == Folder.id)
        .group_by(Folder.id)
        .order_by(Folder.created_at.asc())
        .all()
    )

    return render_base(
        request,
        "chat/_source_selector_modal.html",
        {
            "folders": folders,
        },
    )


@router.post("/modal/source-selector/apply", response_class=HTMLResponse)
async def source_selector_apply(
    request: Request,
    db: OrmSession = Depends(get_db),
    folder_ids: Optional[List[int]] = Form(default=None),
    document_ids: Optional[List[int]] = Form(default=None),
    reset: Optional[str] = Form(default=None),
):
    """
    Apply the selection of folders/documents from the source selector modal.
    - When `reset` is provided, clears all selections.
    - Otherwise, returns a summary fragment with the current selection.
    """
    if reset:
        return render_base(
            request,
            "chat/_source_selection_summary.html",
            {
                "selected_folders": [],
                "selected_documents": [],
                "selected_folder_ids_str": "",
                "selected_document_ids_str": "",
            },
        )

    folder_ids = folder_ids or []
    document_ids = document_ids or []

    selected_folders = []
    selected_documents = []

    if folder_ids:
        selected_folders = (
            db.execute(select(Folder).where(Folder.id.in_(folder_ids)))
            .scalars()
            .all()
        )

    if document_ids:
        selected_documents = (
            db.execute(select(Document).where(Document.id.in_(document_ids)))
            .scalars()
            .all()
        )

    folder_ids_str = ",".join(str(fid) for fid in folder_ids)
    document_ids_str = ",".join(str(did) for did in document_ids)

    return render_base(
        request,
        "chat/_source_selection_summary.html",
        {
            "selected_folders": selected_folders,
            "selected_documents": selected_documents,
            "selected_folder_ids_str": folder_ids_str,
            "selected_document_ids_str": document_ids_str,
        },
        headers={"HX-Trigger": "close-modal"},
    )


@router.post("/modal/source-selector/remove", response_class=HTMLResponse)
async def source_selector_remove(
    request: Request,
    db: OrmSession = Depends(get_db),
    selected_folder_ids: str = Form(""),
    selected_document_ids: str = Form(""),
    remove_folder_id: Optional[int] = Form(default=None),
    remove_document_id: Optional[int] = Form(default=None),
):
    """
    Remove a folder or a document from the current source selection.

    Re-parses the CSV lists coming from hidden fields, updates them,
    and returns an updated selection summary.
    """
    folder_ids = parse_ids_csv(selected_folder_ids)
    document_ids = parse_ids_csv(selected_document_ids)

    if remove_folder_id is not None:
        folder_ids = [fid for fid in folder_ids if fid != remove_folder_id]

    if remove_document_id is not None:
        document_ids = [did for did in document_ids if did != remove_document_id]

    selected_folders = []
    selected_documents = []

    if folder_ids:
        selected_folders = (
            db.execute(select(Folder).where(Folder.id.in_(folder_ids)))
            .scalars()
            .all()
        )

    if document_ids:
        selected_documents = (
            db.execute(select(Document).where(Document.id.in_(document_ids)))
            .scalars()
            .all()
        )

    folder_ids_str = ",".join(str(fid) for fid in folder_ids)
    document_ids_str = ",".join(str(did) for did in document_ids)

    return render_base(
        request,
        "chat/_source_selection_summary.html",
        {
            "selected_folders": selected_folders,
            "selected_documents": selected_documents,
            "selected_folder_ids_str": folder_ids_str,
            "selected_document_ids_str": document_ids_str,
        },
    )


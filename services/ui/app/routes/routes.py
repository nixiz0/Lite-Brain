from typing import Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy import select, func
from sqlalchemy.orm import Session as OrmSession

from CONFIG import ULTRA_MODE_ACTIVE
from app.web_templates import render_base
from i18n import t
from ..db import get_db
from ..models import Folder, Conversation, Document
from ..utils import (
    get_current_conversation_id,
    set_current_conversation_id,
    rendered_messages,
    normalize_messages,
)


router = APIRouter()

# =========== Helper Functions ===========
def sidebar_data(db: OrmSession):
    """
    Load folders (with document count) and conversations for the sidebar.
    
    Folders:
      - ordered by creation date (oldest first)
      - annotated with a doc_count column

    Conversations:
      - ordered by last update (most recent first)
    """
    folders = (
        db.query(Folder, func.count(Document.id).label("doc_count"))
        .outerjoin(Document, Document.folder_id == Folder.id)
        .group_by(Folder.id)
        .order_by(Folder.created_at.asc())
        .all()
    )

    conversations = (
        db.execute(select(Conversation).order_by(Conversation.updated_at.desc()))
        .scalars()
        .all()
    )

    return folders, conversations

def get_or_create_current_conversation(db: OrmSession, request: Request) -> Conversation:
    """
    Resolve the current conversation for the session, creating one if needed.

    Order of precedence:
    1. Use the conversation ID stored in the session (if it exists and is valid).
    2. Fallback to the most recently updated conversation.
    3. If none exists, ensure a default folder and create a new conversation.

    The resolved conversation ID is always persisted back into the session.
    """
    conv_id = get_current_conversation_id(request)
    conv: Optional[Conversation] = db.get(Conversation, conv_id) if conv_id else None

    if not conv:
        # Try to reuse the most recently updated conversation
        conv = (
            db.execute(select(Conversation).order_by(Conversation.updated_at.desc()))
            .scalars()
            .first()
        )

        # Ensure at least one folder exists
        folder = (
            db.execute(select(Folder).order_by(Folder.created_at.asc()))
            .scalars()
            .first()
        )
        if not folder:
            folder = Folder(name=t("fallback_folder_name"))
            db.add(folder)
            db.commit()
            db.refresh(folder)

            # If we just created the first folder and no conversation exists,
            # create a default conversation as well.
            conv = Conversation(
                title=t("new_conversation_title"),
                summary=t("new_conversation_summary"),
                messages=[],
                llm_tier="default",
            )

        if conv is not None:
            db.add(conv)
            db.commit()
            db.refresh(conv)

    set_current_conversation_id(request, conv.id)
    return conv


# =========== Routes Endpoints ===========
@router.get("/", response_class=HTMLResponse)
async def root_redirect(_: Request):
    """
    Redirect root path to the main app entry point.
    """
    return RedirectResponse(url="/app", status_code=HTTP_302_FOUND)


@router.get("/app", response_class=HTMLResponse)
async def app_home(request: Request, db: OrmSession = Depends(get_db)):
    """
    Main chat UI entry point.
    - Ensures a current conversation exists and is bound to the session.
    - Loads messages, folders, and conversations for rendering.
    """
    # Reset any pending "new conversation" flag in the session
    request.session["pending_new"] = False

    conv = get_or_create_current_conversation(db, request)
    msgs = normalize_messages(conv.messages)
    folders, conversations = sidebar_data(db)

    # llm_tier “safe” for the UI
    effective_llm_tier = conv.llm_tier or "default"
    if not ULTRA_MODE_ACTIVE and effective_llm_tier == "ultra":
        effective_llm_tier = "default"

    return render_base(
        request,
        "chat/chat.html",
        {
            "title": conv.title,
            "messages": rendered_messages(msgs),
            "folders": folders,
            "conversations": conversations,
            "current_conversation_id": conv.id,
            "conversation": conv,
            "effective_llm_tier": effective_llm_tier,
            "ultra_mode_active": ULTRA_MODE_ACTIVE,
        },
    )


@router.get("/modal/empty", response_class=HTMLResponse)
async def modal_empty():
    """
    Returns an empty fragment to clear the modal area.

    Used by HTMX to close a modal by replacing #modal-area with empty HTML.
    """
    return HTMLResponse("")


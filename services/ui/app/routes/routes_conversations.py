import logging
logger = logging.getLogger(__name__)

import json, re
from math import ceil
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from starlette.status import HTTP_302_FOUND
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from CONFIG import LLM_MODELS_BY_TIER, LLM_HISTORY_MAX_MESSAGES, MAX_FULL_DOC_CHUNKS, FULL_DOC_CHUNKS_PER_BATCH
from app.web_templates import render_base
from i18n import t
from ..db import get_db
from ..models import Conversation, Document
from ..utils import (
    get_current_conversation_id, set_current_conversation_id,
    make_title_from, rendered_messages, normalize_messages
)
from ..llm.llm_client import call_ollama_chat
from ..llm.mode_preset import MODE_PRESETS
from .functions.time import utc_now_iso
from .functions.parse_ids import parse_ids_csv
from ..rag.rag_pipeline import rag_with_rerank, rag_full_document, build_context_markdown
from ..rag.rag_prompt_system import RAG_PROMPT_SYSTEM
from ..rag.functions.strip_think import strip_think_blocks
from ..rag.functions.batch_chunk import (
    batch_passages, group_passages_by_document, hierarchical_full_doc_answer,
    build_reduce_prompt, build_batch_prompt
)


router = APIRouter()

# =========== Helper Functions ===========
# Regex to remove any block <think>...</think> (across multiple lines)
THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

PROGRESS_DELIM = "\x1e"

def load_messages_for(conv: Conversation) -> List[dict]:
    """
    Normalize a conversation's messages payload into a list of dicts.
    """
    return normalize_messages(conv.messages)

def build_llm_history(messages: List[dict], max_messages: int) -> List[Dict[str, str]]:
    """
    Build the truncated LLM history from a full message list.
    - Keeps only 'user' and 'assistant' messages.
    - For 'assistant' messages, strips any <think>...</think> blocks.
    - Ignores messages without non-empty content.
    - Returns at most `max_messages` messages (most recent last).
    """
    if not messages:
        return []

    trimmed = messages[-max_messages:]
    history: List[Dict[str, str]] = []

    for m in trimmed:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue

        content = (m.get("content") or "").strip()
        if not content:
            continue

        # We only clean assistant messages
        if role == "assistant":
            # Remove all <think>...</think> blocks
            content = THINK_BLOCK_RE.sub("", content).strip()

        if not content:
            # If nothing remains after cleaning, ignore this message.
            continue

        history.append({
            "role": role,
            "content": content,
        })

    return history



# ============== SEND MESSAGE Routes Endpoints ===============
@router.post("/message")
async def post_message(
    request: Request,
    user_input: str = Form(...),

    selected_folder_ids: str = Form("", alias="selected_folder_ids"),
    selected_document_ids: str = Form("", alias="selected_document_ids"),

    llm_tier: str = Form("default"),
    mode_preset: str = Form("free"),
    doc_mode: str = Form("rag"),
    stream_ui: bool = Form(True),  # UI toggle: streaming vs non-streaming

    db: OrmSession = Depends(get_db),
):
    """
    Main endpoint to send a user message in the current conversation.

    Responsibilities:
    - Ensure there is an active conversation (create one if needed).
    - Resolve effective LLM tier, mode preset, and document mode (rag/full).
    - Optionally run RAG on selected folders/documents.
    - Call the LLM in non-stream or stream mode.
    - Persist both user and assistant messages in the conversation.
    """
    pending = request.session.pop("pending_new", False)
    conv_id = get_current_conversation_id(request)
    conv: Conversation | None = db.get(Conversation, conv_id) if conv_id else None

    # 1) Create a new conversation if requested or if none exists
    if pending or not conv:
        title = make_title_from(user_input)
        now = datetime.utcnow()
        last_tier = request.session.get("last_llm_tier", "default")
        conv = Conversation(
            title=title,
            summary=title,
            created_at=now,
            updated_at=now,
            msg_count=0,
            messages=[],
            llm_tier=last_tier,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        set_current_conversation_id(request, conv.id)

    # Ensure messages is a list we can append to
    if conv.messages is None:
        conv.messages = []

    # 2) Parse selected folder / document IDs from form CSV values
    folder_ids: List[int] = parse_ids_csv(selected_folder_ids)
    document_ids: List[int] = parse_ids_csv(selected_document_ids)

    # If only document_ids are provided, infer folder_ids from associated documents
    if not folder_ids and document_ids:
        docs = (
            db.execute(
                select(Document).where(Document.id.in_(document_ids))
            )
            .scalars()
            .all()
        )

        if not docs:
            logger.warning(
                "post_message: document_ids provided but no document found in database: %s",
                document_ids,
            )
            folder_ids = []
            document_ids = []
        else:
            folder_ids = sorted(
                {
                    d.folder_id
                    for d in docs
                    if getattr(d, "folder_id", None) is not None
                }
            )
            document_ids = sorted({d.id for d in docs})

    # Debug traces for selected RAG scope
    print("API folder_ids: ", folder_ids)
    print("API document_ids: ", document_ids)

    # 2.bis Resolve effective LLM tier for this request
    raw_form_tier = (llm_tier or "").strip() or None
    base_tier = conv.llm_tier or "default"
    effective_tier = raw_form_tier or base_tier
    if effective_tier not in LLM_MODELS_BY_TIER:
        effective_tier = "default"

    request.session["last_llm_tier"] = effective_tier

    model_name = LLM_MODELS_BY_TIER[effective_tier]
    conv.llm_tier = effective_tier

    # 2.ter Resolve effective mode preset for this conversation
    raw_preset = (mode_preset or "").strip() or None
    base_preset = getattr(conv, "mode_preset", None) or "free"
    effective_preset = raw_preset or base_preset
    if effective_preset not in MODE_PRESETS:
        effective_preset = "free"

    # 2.quator Resolve effective document mode: RAG vs full-document
    doc_mode = (doc_mode or "rag").strip().lower()
    if doc_mode not in ("rag", "full"):
        doc_mode = "rag"

    request.session["last_mode_preset"] = effective_preset
    conv.mode_preset = effective_preset

    preset_cfg = MODE_PRESETS[effective_preset]
    system_mode_prompt: str = preset_cfg.get("system", "")

    # Base temperature (may be overridden when RAG is used)
    temperature: float = float(preset_cfg.get("temperature", 0.7))

    # 3) Append current user message to the conversation
    now_iso = utc_now_iso()
    conv.messages.append({
        "role": "user",
        "content": user_input,
        "ts": now_iso,
        "source_folders": folder_ids,
        "source_documents": document_ids,
        "llm_tier": effective_tier,
        "mode_preset": effective_preset,
        "doc_mode": doc_mode,
    })
    previous_messages = conv.messages[:-1]
    history_prev = build_llm_history(previous_messages, LLM_HISTORY_MAX_MESSAGES)

    # 4) Build messages and context for the LLM (with or without RAG)
    sources: List[Dict[str, Any]] = []
    use_rag = bool(folder_ids or document_ids)

    llm_messages: List[Dict[str, str]] = []
    passages: List[Dict[str, Any]] = []

    # System messages common to all LLM calls
    system_messages: List[Dict[str, str]] = []
    if system_mode_prompt:
        system_messages.append({
            "role": "system",
            "content": system_mode_prompt,
        })

    if use_rag:
        try:
            is_full_docs_mode = (effective_preset == "docs" and doc_mode == "full")

            if is_full_docs_mode:
                # Full-document hierarchical mode: retrieve ALL relevant chunks
                passages = rag_full_document(
                    folder_ids=folder_ids,
                    document_ids=document_ids,
                )
            else:
                # Standard RAG mode: targeted retrieval + rerank
                passages = rag_with_rerank(
                    query=user_input,
                    folder_ids=folder_ids,
                    document_ids=document_ids,
                )
        except Exception as e:
            logger.exception("RAG error in post_message: %s", e)
            passages = []
            is_full_docs_mode = False  # safety fallback

        # Build sources list for UI display regardless of RAG strategy
        for p in passages or []:
            sources.append({
                "file_name": p.get("file_name"),
                "document_id": p.get("document_id"),
                "chunk_index": p.get("chunk_index"),
                "text": (p.get("text") or "").strip(),
            })

        if passages:
            # When RAG is used, prefer the RAG-specific temperature if defined
            temperature = float(
                preset_cfg.get("temperature_rag", preset_cfg.get("temperature", 0.7))
            )

            if is_full_docs_mode:
                # Hierarchical full-doc mode:
                # do NOT build a giant ctx_md here; hierarchical_full_doc_* uses `passages` directly
                llm_messages = []
            else:
                # Standard RAG: inline retrieved context ahead of the user question
                ctx_md = build_context_markdown(passages)

                user_content = (
                    f"{ctx_md}\n\n"
                    "---\n\n"
                    f"User question :\n{user_input}"
                )

                llm_messages = (
                    system_messages
                    + [{"role": "system", "content": RAG_PROMPT_SYSTEM}]
                    + history_prev
                    + [{"role": "user", "content": user_content}]
                )
        else:
            # No passages retrieved → fallback to pure chat with history
            temperature = float(preset_cfg.get("temperature", 0.7))
            llm_messages = (
                system_messages
                + history_prev
                + [{"role": "user", "content": user_input}]
            )
    else:
        # No RAG requested: standard chat with conversation history
        temperature = float(preset_cfg.get("temperature", 0.7))
        llm_messages = (
            system_messages
            + history_prev
            + [{"role": "user", "content": user_input}]
        )

    # 5) LLM call: non-streaming vs streaming (UI mode)
    if not stream_ui:
        # ===== Non-stream mode: single-shot answer, returned as HTML fragment (HTMX) =====
        # Special case: docs + full → hierarchical pipeline on the entire document
        if use_rag and effective_preset == "docs" and doc_mode == "full":
            try:
                assistant_raw_content = hierarchical_full_doc_answer(
                    user_query=user_input,
                    passages=passages,
                    model_name=model_name,
                    temperature=temperature,
                )
            except Exception as e:
                logger.exception("Error in hierarchical full-doc pipeline: %s", e)
                assistant_raw_content = t("error_full_doc_unavailable").format(
                    message=user_input.strip()
                )
        else:
            # Default behavior: normal chat or standard RAG
            try:
                assistant_raw_content = call_ollama_chat(
                    model=model_name,
                    messages=llm_messages,
                    stream=False,
                    think=True,
                    temperature=temperature,
                )
            except Exception as e:
                logger.exception("LLM error (non-stream): %s", e)
                assistant_raw_content = t("error_model_unavailable").format(
                    message=user_input.strip()
                )

        # Persist assistant message and update conversation metadata
        conv.messages.append({
            "role": "assistant",
            "content": assistant_raw_content,
            "ts": utc_now_iso(),
            "rag_sources": sources,
            "llm_tier": effective_tier,
            "mode_preset": effective_preset,
        })

        conv.msg_count = len(conv.messages)
        conv.updated_at = datetime.utcnow()
        if not conv.summary:
            conv.summary = conv.title or make_title_from(user_input)

        db.commit()

        tail = rendered_messages(conv.messages[-1:])
        headers = {"HX-Trigger": "refresh-conversations"}

        return render_base(
            request,
            "chat/_messages.html",
            {"messages": tail},
            headers=headers
        )

    # ===== stream_ui = True: stream tokens back as plain text =====
    def token_generator():
        """
        Stream LLM tokens and persist the final assistant message.
        - Normal / targeted RAG: directly stream from the LLM.
        - Docs + Full: group passages by document (same logic as non-stream),
          run a hierarchical MAP + REDUCE pipeline per document, and stream the
          final answers with progress events.
        """
        answer_buffer: list[str] = []

        try:
            # Special case: hierarchical full-doc mode (Docs + Full)
            if use_rag and effective_preset == "docs" and doc_mode == "full":
                # Ensure we have a list of passages to work with
                effective_passages = passages or []

                if not effective_passages:
                    msg = t("rag_no_relevant_info")
                    answer_buffer.append(msg)
                    yield msg
                    return

                # Global safety guard: hard-limit total number of chunks
                if len(effective_passages) > MAX_FULL_DOC_CHUNKS:
                    effective_passages = effective_passages[:MAX_FULL_DOC_CHUNKS]

                chunks_per_batch = FULL_DOC_CHUNKS_PER_BATCH

                # ===== 1) Group passages by (document_id, file_name) =====
                # Reuse the same helper as in the non-stream pipeline
                ordered_keys, doc_groups = group_passages_by_document(effective_passages)

                # If for some reason no grouping is possible, bail out gracefully
                if not ordered_keys:
                    msg = t("rag_no_relevant_info")
                    answer_buffer.append(msg)
                    yield msg
                    return

                # Compute the total number of MAP batches across all documents
                # so that progress events are global and monotonic.
                total_batches = 0
                for key in ordered_keys:
                    doc_passages = doc_groups.get(key) or []
                    if doc_passages:
                        total_batches += ceil(len(doc_passages) / chunks_per_batch)

                batch_index = 0  # global batch counter for progress

                # ===== 2) Process each document independently (MAP + REDUCE) =====
                first_doc = True  # used to avoid a leading "---" separator

                for doc_id, file_name in ordered_keys:
                    doc_passages = doc_groups.get((doc_id, file_name)) or []

                    if not doc_passages:
                        # No passages for this document → skip
                        continue

                    partial_results: List[str] = []

                    # ----- MAP phase for THIS document -----
                    for batch in batch_passages(
                        doc_passages,
                        chunks_per_batch=chunks_per_batch,
                    ):
                        batch_index += 1

                        ctx_md = build_context_markdown(batch)
                        prompt = build_batch_prompt(ctx_md, user_input)

                        try:
                            batch_answer = call_ollama_chat(
                                model=model_name,
                                messages=[{"role": "user", "content": prompt}],
                                stream=False,
                                think=True,
                                temperature=temperature,
                            )
                        except Exception as e:
                            logger.exception(
                                "LLM error in hierarchical_full_doc_partial MAP phase "
                                "(stream, doc_id=%s): %s",
                                doc_id,
                                e,
                            )
                            # Still emit progress so UI can move forward
                            progress_token = (
                                f"{PROGRESS_DELIM}"
                                f"__PROGRESS__:{batch_index}:{total_batches}"
                                f"{PROGRESS_DELIM}"
                            )
                            yield progress_token
                            continue

                        if not batch_answer:
                            # Nothing returned for this batch → still emit progress
                            progress_token = (
                                f"{PROGRESS_DELIM}"
                                f"__PROGRESS__:{batch_index}:{total_batches}"
                                f"{PROGRESS_DELIM}"
                            )
                            yield progress_token
                            continue

                        # Strip <think>...</think> from the intermediate answer
                        text = strip_think_blocks(batch_answer)

                        if not text:
                            # Nothing left after stripping → ignore but still emit progress
                            progress_token = (
                                f"{PROGRESS_DELIM}"
                                f"__PROGRESS__:{batch_index}:{total_batches}"
                                f"{PROGRESS_DELIM}"
                            )
                            yield progress_token
                            continue

                        normalized = text.strip().upper()

                        # Ignore explicit "__NO_INFO__" signals returned by the model
                        if normalized == "__NO_INFO__" or normalized == "NO_INFO":
                            progress_token = (
                                f"{PROGRESS_DELIM}"
                                f"__PROGRESS__:{batch_index}:{total_batches}"
                                f"{PROGRESS_DELIM}"
                            )
                            yield progress_token
                            continue

                        # Optional prefix normalization: drop leading "INFO:" if present
                        if text.startswith("INFO:"):
                            text = text[len("INFO:"):].lstrip()

                        partial_results.append(text)

                        # Emit progress event after each processed batch
                        progress_token = (
                            f"{PROGRESS_DELIM}"
                            f"__PROGRESS__:{batch_index}:{total_batches}"
                            f"{PROGRESS_DELIM}"
                        )
                        yield progress_token

                    # ----- End of MAP phase for this document -----
                    if not partial_results:
                        # No useful information found for this document → skip it
                        continue

                    # ----- 3) REDUCE phase for THIS document -----
                    # We ALWAYS run a streamed REDUCE call, even if there is only one
                    # partial result. This ensures the final per-document answer can
                    # include a <think>...</think> block, while MAP answers remain clean.
                    reduce_prompt = build_reduce_prompt(partial_results, user_input)

                    # Add an optional separator between documents
                    if not first_doc:
                        sep = "\n\n---\n\n"
                        answer_buffer.append(sep)
                        yield f"{PROGRESS_DELIM}{sep}{PROGRESS_DELIM}"
                    first_doc = False

                    title = file_name or f"Document {doc_id}"
                    heading = f"## {title} (Document ID: {doc_id})\n\n"
                    answer_buffer.append(heading)
                    # Heading is sent as normal assistant content
                    yield f"{PROGRESS_DELIM}{heading}{PROGRESS_DELIM}"

                    try:
                        # REDUCE phase streamed from the LLM for THIS document
                        stream_iter = call_ollama_chat(
                            model=model_name,
                            messages=[{"role": "user", "content": reduce_prompt}],
                            stream=True,
                            think=True,  # allow the model to send <think> for the final answer
                            temperature=temperature,
                        )
                        for delta in stream_iter:
                            answer_buffer.append(delta)
                            # Wrap each delta with PROGRESS_DELIM for the client protocol
                            yield f"{PROGRESS_DELIM}{delta}{PROGRESS_DELIM}"

                    except Exception as e:
                        logger.exception(
                            "LLM error in hierarchical_full_doc REDUCE phase "
                            "(stream_ui=True, doc_id=%s): %s",
                            doc_id,
                            e,
                        )
                        # Fallback: concatenate all partial answers for this document
                        fallback = "\n\n---\n\n".join(partial_results)
                        answer_buffer.append(fallback)
                        yield f"{PROGRESS_DELIM}{fallback}{PROGRESS_DELIM}"

                # If after processing all documents there is still no answer, send a default message
                if not answer_buffer:
                    msg = t("rag_no_relevant_info")
                    answer_buffer.append(msg)
                    yield msg

            else:
                # Default streaming behavior (normal chat / targeted RAG)
                stream_iter = call_ollama_chat(
                    model=model_name,
                    messages=llm_messages,
                    stream=True,
                    think=True,
                    temperature=temperature,
                )
                for delta in stream_iter:
                    answer_buffer.append(delta)
                    yield delta

        except Exception as e:
            logger.exception("LLM streaming error: %s", e)
            err_msg = f"\n\n[{t('error_calling_model')}]"
            answer_buffer.append(err_msg)
            yield err_msg

        finally:
            # Persist the full streamed answer in the conversation
            full_text = "".join(answer_buffer) if answer_buffer else ""
            conv.messages.append({
                "role": "assistant",
                "content": full_text,
                "ts": utc_now_iso(),
                "rag_sources": sources,
                "llm_tier": effective_tier,
                "mode_preset": effective_preset,
            })

            conv.msg_count = len(conv.messages)
            conv.updated_at = datetime.utcnow()
            if not conv.summary:
                conv.summary = conv.title or make_title_from(user_input)

            db.commit()

    return StreamingResponse(token_generator(), media_type="text/plain")



# ============== CRUD CONVERSATIONS Routes Endpoints ===============
@router.post("/conversations/current/llm-tier", response_class=HTMLResponse)
async def update_current_conv_llm_tier(
    request: Request,
    llm_tier: str = Form("default"),
    db: OrmSession = Depends(get_db),
):
    """
    Update the LLM tier for the current conversation and persist it in session.
    """
    conv_id = get_current_conversation_id(request)
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail=t("error_conversation_not_found"))

    if llm_tier not in LLM_MODELS_BY_TIER:
        llm_tier = "default"

    conv.llm_tier = llm_tier
    conv.updated_at = datetime.utcnow()
    db.commit()

    request.session["last_llm_tier"] = llm_tier
    return HTMLResponse("")


@router.get("/conversations/current/messages", response_class=HTMLResponse)
async def current_conversation_messages(
    request: Request,
    db: OrmSession = Depends(get_db),
):
    """
    Return the messages for the current conversation as an HTML fragment.
    Also sends HX triggers to refresh sidebar and LLM tier state on the client.
    """
    conv_id = get_current_conversation_id(request)
    conv: Conversation | None = db.get(Conversation, conv_id) if conv_id else None

    if not conv:
        # No current conversation: return an empty chat fragment
        return render_base(
            request,
            "chat/_messages.html",
            {"messages": []},
        )

    msgs = load_messages_for(conv)

    hx_trigger_payload = {
        "refresh-conversations": True,
        "set-llm-tier": conv.llm_tier or "default",
    }
    headers = {"HX-Trigger": json.dumps(hx_trigger_payload)}

    return render_base(
        request,
        "chat/_messages.html",
        {"messages": rendered_messages(msgs)},
        headers=headers,
    )


@router.get("/conversations/{conv_id}", response_class=HTMLResponse)
async def switch_conversation(conv_id: int, request: Request, db: OrmSession = Depends(get_db)):
    """
    Switch the active conversation in the session and return its messages.

    If the request comes from HTMX, returns only the messages fragment,
    otherwise performs a full redirect to /app.
    """
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail=t("error_conversation_not_found"))

    set_current_conversation_id(request, conv.id)
    request.session["pending_new"] = False

    msgs = load_messages_for(conv)
    hx_trigger_payload = {
        "refresh-conversations": True,
        "set-llm-tier": conv.llm_tier or "default",
    }
    headers = {"HX-Trigger": json.dumps(hx_trigger_payload)}

    if request.headers.get("HX-Request") == "true":
        return render_base(
            request,
            "chat/_messages.html",
            {"messages": rendered_messages(msgs)},
            headers=headers
        )

    return RedirectResponse(url="/app", status_code=HTTP_302_FOUND)


@router.post("/conversations/new", response_class=HTMLResponse)
async def new_conversation_pending(
    request: Request,
    llm_tier: str = Form("default"),
):
    """
    Mark the session so that the next message will start a new conversation.
    Only resets conversation state, the new Conversation row is created on /message.
    """
    request.session["pending_new"] = True
    request.session.pop("current_conversation_id", None)

    # Remember desired tier for the next created conversation
    request.session["last_llm_tier"] = llm_tier

    headers = {"HX-Trigger": json.dumps({"set-llm-tier": llm_tier})}

    return render_base(
        request,
        "chat/_messages.html",
        {"messages": []},
        headers=headers
    )


@router.get("/sidebar/conversations", response_class=HTMLResponse)
async def conversations_fragment(request: Request, db: OrmSession = Depends(get_db)):
    """
    Sidebar fragment: list all conversations ordered by most recent update.
    """
    conversations = db.execute(
        select(Conversation).order_by(Conversation.updated_at.desc())
    ).scalars().all()

    return render_base(
        request,
        "conversations/_conversations.html",
        {
            "conversations": conversations,
            "current_conversation_id": get_current_conversation_id(request),
        },
    )


@router.get("/conversations/{conv_id}/title/edit", response_class=HTMLResponse)
async def edit_conversation_title(conv_id: int, request: Request, db: OrmSession = Depends(get_db)):
    """
    Render the inline edit form for a conversation title.
    """
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail=t("error_conversation_not_found"))

    return render_base(
        request,
        "conversations/_conversation_title_edit.html",
        {"conv": conv},
    )


@router.post("/conversations/{conv_id}/rename", response_class=HTMLResponse)
async def rename_conversation(
    conv_id: int,
    request: Request,
    title: str = Form(...),
    db: OrmSession = Depends(get_db),
):
    """
    Rename a conversation and refresh its link in the sidebar.
    """
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail=t("error_conversation_not_found"))

    new_title = (title or "").strip()
    if not new_title:
        raise HTTPException(status_code=400, detail=t("error_title_empty"))
    new_title = new_title[:120]

    conv.title = new_title
    if not conv.summary:
        conv.summary = new_title
    conv.updated_at = datetime.utcnow()
    db.commit()

    headers = {"HX-Trigger": "refresh-conversations"}
    return render_base(
        request,
        "conversations/_conversation_link.html",
        {
            "c": conv,
            "current_conversation_id": get_current_conversation_id(request),
        },
        headers=headers
    )


@router.delete("/conversations/{conv_id}", response_class=HTMLResponse)
async def delete_conversation(conv_id: int, request: Request, db: OrmSession = Depends(get_db)):
    """
    Delete a conversation and select the next one, creating a default if needed.
    """
    conv = db.get(Conversation, conv_id)
    if conv:
        db.delete(conv)
        db.commit()

    # Pick the next most recent conversation or create a default one
    next_conv = db.execute(
        select(Conversation).order_by(Conversation.updated_at.desc())
    ).scalars().first()

    if not next_conv:
        next_conv = Conversation(
            title=t("new_conversation_title"),
            summary=t("new_conversation_summary"),
            messages=[{...}],  # placeholder preserved as in original code
            msg_count=1,
            updated_at=datetime.utcnow(),
            llm_tier=request.session.get("last_llm_tier", "default"),
        )

        db.add(next_conv)
        db.commit()
        db.refresh(next_conv)

    set_current_conversation_id(request, next_conv.id)
    headers = {"HX-Trigger": "refresh-conversations"}

    return render_base(
        request,
        "chat/_messages.html",
        {
            "messages": rendered_messages(
                normalize_messages(next_conv.messages)
            ),
        },
        headers=headers
    )


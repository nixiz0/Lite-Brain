import json
from typing import List, Optional, Dict, Any
from fastapi import Request

from .markdown_utils import safe_markdown, render_assistant_content


# =========== Functions for Conversations ===========
def get_current_conversation_id(request: Request) -> Optional[int]:
    """
    Retrieve the current conversation ID stored in the user's session.
    Returns None if no conversation has been set.
    """
    return request.session.get("current_conversation_id")

def set_current_conversation_id(request: Request, conv_id: int):
    """
    Persist the given conversation ID in the user's session.
    """
    request.session["current_conversation_id"] = conv_id

def make_title_from(text: str, max_chars: int = 60, max_words: int = 8) -> str:
    """
    Build a short, human-readable title from a user message.
    - Uses the first non-empty line of `text`.
    - Truncates to at most `max_words` words and `max_chars` characters.
    - Strips trailing punctuation.
    - Falls back to 'Conversation ???' when `text` is empty/invalid.
    """
    line = (text or "").strip().splitlines()[0]
    words = line.split()
    if len(words) > max_words:
        line = " ".join(words[:max_words])
    line = line[:max_chars].rstrip(" ,.;:!?-")
    return line or "Conversation ???"


# =========== Functions for messages in conversation ===========
def normalize_messages(raw: Any) -> List[Dict[str, Any]]:
    """
    Normalize a raw messages payload to a list of message dicts.
    Accepted inputs:
    - None          -> []
    - JSON string   -> parsed list or []
    - list          -> returned as-is
    Any parsing error or unsupported type results in an empty list.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            return json.loads(raw) or []
        except Exception:
            # Invalid JSON or unexpected structure: treat as no messages
            return []
    if isinstance(raw, list):
        return raw
    return []

def rendered_messages(messages: List[Dict[str, Any]]) -> list:
    """
    Render a list of raw message dicts into HTML-ready structures.
    Each output item contains:
    - role:        message author ('assistant', 'user', etc.), defaults to 'assistant'
    - ts:          timestamp field as passed through (or empty string)
    - html:        HTML-rendered content (assistant uses think renderer, others markdown)
    - rag_sources: retrieval metadata passed through unchanged
    """
    out = []
    for m in messages:
        role = m.get("role") or "assistant"
        content = m.get("content") or ""
        ts = m.get("ts") or ""
        rag_sources = m.get("rag_sources") or []

        if role == "assistant":
            html = render_assistant_content(content)
        else:
            html = safe_markdown(content)

        out.append({
            "role": role,
            "ts": ts,
            "html": html,
            "rag_sources": rag_sources,
        })
    return out

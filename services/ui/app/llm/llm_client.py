import json, requests
from typing import List, Dict, Iterator
from CONFIG import OLLAMA_URL, OLLAMA_TIMEOUT_S


# =========== Helper Streaming LLM Function ===========
def _stream_ollama_chat(
    model: str,
    messages: List[Dict[str, str]],
    think: bool | str | None = True,
    options: Dict[str, object] | None = None,
) -> Iterator[str]:
    """
    Low-level streaming interface for Ollama /api/chat.
    Yields text chunks in order, already merged into:
        <think>...streamed thinking...</think>...streamed answer...
    """
    url = OLLAMA_URL.rstrip("/") + "/api/chat"
    payload: Dict[str, object] = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    # Include reasoning flag when explicitly provided
    if think is not None:
        payload["think"] = think

    if options:
        payload["options"] = options

    with requests.post(url, json=payload, stream=True, timeout=OLLAMA_TIMEOUT_S) as resp:
        resp.raise_for_status()

        in_thinking = False  # Tracks whether we are inside <think>...</think> tags

        for line in resp.iter_lines():
            if not line:
                continue

            try:
                data = json.loads(line.decode("utf-8"))
            except Exception:
                continue

            msg = data.get("message") or {}
            if not isinstance(msg, dict):
                msg = {}

            # Either field may contain partial text, depending on Ollama version
            thinking_chunk = msg.get("thinking") or data.get("thinking") or ""
            content_chunk = msg.get("content") or data.get("content") or ""

            # ----- Thinking phase -----
            if thinking_chunk:
                if not in_thinking:
                    in_thinking = True
                    yield "<think>"
                yield thinking_chunk

            # ----- Final answer phase -----
            if content_chunk:
                if in_thinking:
                    in_thinking = False
                    yield "</think>"
                yield content_chunk

            # End of stream
            if data.get("done"):
                if in_thinking:
                    in_thinking = False
                    yield "</think>"
                break


# =========== Final Chat Function ===========
def call_ollama_chat(
    model: str,
    messages: List[Dict[str, str]],
    stream: bool = False,
    think: bool | str | None = True,
    options: Dict[str, object] | None = None,
    temperature: float | None = None,
):
    """
    Public API wrapper.
    - stream=False → returns the full response as a string.
    - stream=True  → returns a generator yielding streamed text chunks.

    Returned text already includes <think>...</think> sections if supported.
    """
    # Merge temperature into options if provided
    if temperature is not None:
        options = dict(options or {})
        options["temperature"] = float(temperature)

    if stream:
        # Return generator directly
        return _stream_ollama_chat(model=model, messages=messages, think=think, options=options)

    # Non-streaming mode: accumulate all streamed chunks
    chunks: List[str] = []
    for delta in _stream_ollama_chat(model=model, messages=messages, think=think, options=options):
        chunks.append(delta)

    return "".join(chunks)

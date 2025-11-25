import re

def strip_think_blocks(text: str) -> str:
    """
    Remove all <think>...</think> (chain-of-thought) blocks and return only visible text.
    """
    if not text:
        return text

    # Remove any <think>...</think> blocks (multi-line, case-insensitive)
    cleaned = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    return cleaned.strip()

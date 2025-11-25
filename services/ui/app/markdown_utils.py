import bleach, mistune, html
from typing import List
from mistune import HTMLRenderer
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from i18n import t


# =========== HTML sanitization config for rendered markdown ===========
ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "p", "pre", "code", "blockquote", "hr", "br", "span", "img",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
    "ul", "ol", "li", "a", "strong", "em", "del", "sup", "sub",
    "details", "summary",
}

ALLOWED_ATTRS = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "rel", "target"],
    "img": ["src", "alt", "title", "width", "height", "loading", "decoding"],
    "code": ["class"],
    "span": ["class"],
    "pre": ["class"],
}


# =========== Helper Class / Functions ===========
class PygmentsRenderer(HTMLRenderer):
    """
    HTML renderer for Mistune that injects syntax-highlighted code blocks using Pygments.
    """

    def block_code(self, code, info=None):
        """
        Render fenced code blocks with syntax highlighting.
        - Uses `info` to determine the language when provided.
        - Falls back to language guessing when `info` is absent.
        - On error, escapes the code and renders without highlighting.
        - Uses inline styles (noclasses=True) so no external CSS file is required.
        """
        try:
            if info:
                lang = info.strip().split()[0]
                lexer = get_lexer_by_name(lang, stripall=True)
            else:
                lexer = guess_lexer(code)

            formatter = HtmlFormatter(nowrap=True, noclasses=True)
            highlighted = highlight(code, lexer, formatter)

            return (
                '<pre class="rounded-xl overflow-x-auto border border-slate-700 bg-slate-900/60">'
                f"<code>{highlighted}</code></pre>"
            )
        except Exception:
            # Fallback: render escaped plain-text code
            from mistune.util import escape
            return (
                '<pre class="rounded-xl overflow-x-auto border border-slate-700 bg-slate-900/60">'
                f"<code>{escape(code)}</code></pre>"
            )

def render_think_details(think: str) -> str:
    """
    Internal helper to wrap a <think> block into a <details> HTML snippet.
    The `think` content is escaped to avoid injecting HTML.
    """
    escaped = html.escape((think or "").strip())
    think_text = t("think_mode")

    return f"""
<details class="mt-3 text-xs text-slate-300 border border-slate-700/70 rounded-lg bg-slate-900/60 p-3 think-block">
  <summary class="cursor-pointer select-none flex items-center gap-1 hover:text-slate-100">
    <span>{think_text}</span>
  </summary>
  <pre class="mt-2 whitespace-pre-wrap text-[11px] leading-relaxed">{escaped}</pre>
</details>
    """.strip()


# =========== Safe Markdown Rendering ===========
# Configure Mistune with the custom renderer and common markdown extensions
renderer = PygmentsRenderer()
markdown = mistune.create_markdown(
    renderer=renderer,
    plugins=["strikethrough", "table", "task_lists", "footnotes", "url"],
)

def safe_markdown(md_text: str) -> str:
    """
    Convert markdown to sanitized HTML.
    The HTML:
    - is rendered using Mistune + Pygments
    - is cleaned with Bleach to enforce allowed tags/attributes
    """
    html_output = markdown(md_text or "")
    return bleach.clean(html_output, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

def render_assistant_content(raw: str) -> str:
    """
    Render assistant output supporting MULTIPLE <think> blocks.

    Behavior:
    - Any text outside <think>...</think> is rendered as sanitized markdown.
    - Each <think>...</think> section is rendered as a collapsible <details> block.
    - If a <think> is opened but not yet closed (streaming artefact),
      its content is still wrapped in a <details> block, without any "after".
    - If no <think> tag is present at all, the whole content is rendered as markdown.
    """
    content = raw or ""
    if "<think>" not in content:
        return safe_markdown(content)

    parts: List[str] = []
    think_open = "<think>"
    think_close = "</think>"

    idx = 0
    n = len(content)

    while idx < n:
        start = content.find(think_open, idx)

        # No more <think> → trailing markdown.
        if start == -1:
            trailing = content[idx:]
            if trailing.strip():
                parts.append(safe_markdown(trailing))
            break

        # Text before this <think> → normal markdown.
        if start > idx:
            before = content[idx:start]
            if before.strip():
                parts.append(safe_markdown(before))

        # Look for the closing tag.
        end = content.find(think_close, start + len(think_open))

        # Case: open <think> but no closing </think> → treat rest as thinking.
        if end == -1:
            think_body = content[start + len(think_open):]
            parts.append(render_think_details(think_body))
            break

        # Normal case: full <think>...</think> block.
        think_body = content[start + len(think_open):end]
        parts.append(render_think_details(think_body))

        # Continue after </think>.
        idx = end + len(think_close)

    # Fallback (should not happen, but just in case).
    if not parts:
        parts.append(safe_markdown(content))

    return "\n".join(parts)

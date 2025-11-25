// ======= Helper Functions =======
/**
 * Escape user-provided text for safe HTML insertion.
 *
 * - Replaces &, <, >, ", ' with their HTML entities
 * - Always returns a string (empty string if input is null/undefined)
 */
function escapeHtml(str) {
  return (str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Build the HTML string for a user message bubble.
 *
 * - Escapes HTML and converts line breaks to <br>
 * - Right-aligns the bubble and adds a "U" avatar
 */
function userBubbleHtml(text) {
  const escaped = escapeHtml(text).replace(/\n/g, "<br>");
  return `
    <div class="flex items-start gap-3 justify-end">
      <div class="max-w-[75ch] md:max-w-[85ch]
                  bg-slate-900/70 border border-slate-800 rounded-2xl px-4 py-3 shadow-sm ml-auto
                  prose prose-invert prose-headings:font-semibold prose-pre:shadow-inner prose-img:rounded-xl
                  prose-a:text-cyan-400 hover:prose-a:text-cyan-300">
        ${escaped}
      </div>
      <div class="w-8 h-8 rounded-full bg-slate-700 text-white grid place-content-center">U</div>
    </div>
  `;
}


// ======= Full-doc progress helpers =======
// Special delimiter used by the backend to multiplex progress + text in the stream.
const PROGRESS_DELIM = "\u001e";

/**
 * Show or hide the full-doc progress container.
 */
function setFullDocProgressVisible(visible) {
  const container = document.getElementById("full-doc-progress");
  if (!container) return;
  container.classList.toggle("hidden", !visible);
}

/**
 * Reset full-doc progress UI to the initial state.
 */
function resetFullDocProgress() {
  const bar = document.getElementById("full-doc-progress-bar");
  const label = document.getElementById("full-doc-progress-label");
  if (bar) bar.style.width = "0%";
  if (label) label.textContent = "0 / 0";
}

/**
 * Update the full-doc progress bar and label with the current batch counts.
 */
function updateFullDocProgress(done, total) {
  const bar = document.getElementById("full-doc-progress-bar");
  const label = document.getElementById("full-doc-progress-label");
  if (!bar || !label) return;

  const ratio = total > 0 ? Math.min(done / total, 1) : 0;
  const percent = Math.round(ratio * 100);

  bar.style.width = `${percent}%`;
  label.textContent = `${percent} % (${done}/${total})`;
}

/**
 * Build the HTML string for an assistant message bubble.
 *
 * - Wraps a target <div> identified by msgId where streamed tokens are rendered
 */
function assistantBubbleHtml(msgId) {
  return `
    <div class="flex items-start gap-3">
      <div class="w-8 h-8 rounded-full bg-slate-200 text-slate-900 grid place-content-center">A</div>
      <div class="max-w-[75ch] md:max-w-[85ch]
                  bg-slate-800/70 border border-slate-700 rounded-2xl px-4 py-3 shadow-sm
                  prose prose-invert prose-headings:font-semibold prose-pre:shadow-inner prose-img:rounded-xl
                  prose-a:text-cyan-400 hover:prose-a:text-cyan-300">
        <div id="${msgId}" class="text-sm whitespace-pre-wrap leading-relaxed"></div>
      </div>
    </div>
  `;
}

/**
 * Render assistant content, splitting visible text and <think> blocks.
 *
 * - Supports multiple <think>...</think> blocks in a single message
 * - Supports streaming: the last <think> block may be incomplete (no closing tag yet)
 * - Renders visible text as plain text (no Markdown)
 * - Wraps each <think> block in a collapsible <details> debug section
 */
function renderWithThink(raw, container) {
  const content = raw || "";

  // Fast path: no <think> blocks, render as plain text
  if (!content.includes("<think>")) {
    container.textContent = content;
    return;
  }

  const THINK_OPEN = "<think>";
  const THINK_CLOSE = "</think>";

  /**
   * Append a visible (non-thinking) text chunk as a simple <div>.
   * Skips empty / whitespace-only chunks.
   */
  const appendTextBlock = (text) => {
    if (!text || !text.trim()) return;
    const div = document.createElement("div");
    div.textContent = text;
    container.appendChild(div);
  };

  /**
   * Append a <think> block wrapped in a <details> element.
   * When isStreaming is true, the block is left open and labeled as streaming.
   */
  const appendThinkBlock = (thinkText, { isStreaming = false } = {}) => {
    const details = document.createElement("details");
    details.className =
      "mt-3 text-xs text-slate-300 border border-slate-700/70 rounded-lg bg-slate-900/60 p-3 think-block";

    // Keep the block expanded while the model is still streaming its thoughts
    if (isStreaming) {
      details.setAttribute("open", "open");
    }

    const summary = document.createElement("summary");
    summary.className =
      "cursor-pointer select-none flex items-center gap-1 hover:text-slate-100";
    summary.innerHTML = isStreaming
      ? `<span>🧠 Model thinking (streaming)...</span>`
      : `<span>🧠 Model thinking (finished)</span>`;
    details.appendChild(summary);

    const pre = document.createElement("pre");
    pre.className = "mt-2 whitespace-pre-wrap text-[11px] leading-relaxed";
    pre.textContent = (thinkText || "").trim();
    details.appendChild(pre);

    container.appendChild(details);
  };

  // Rebuild the entire container for each chunk (idempotent render)
  container.innerHTML = "";

  let index = 0;
  const length = content.length;

  while (index < length) {
    const start = content.indexOf(THINK_OPEN, index);

    // No more <think> tags: append the remaining visible text and stop
    if (start === -1) {
      const tail = content.slice(index);
      appendTextBlock(tail);
      break;
    }

    // Append visible text that appears before the next <think> block
    if (start > index) {
      const before = content.slice(index, start);
      appendTextBlock(before);
    }

    const closeStart = content.indexOf(
      THINK_CLOSE,
      start + THINK_OPEN.length
    );

    // STREAMING CASE: <think> is open but not yet closed
    if (closeStart === -1) {
      const thinkSoFar = content.slice(start + THINK_OPEN.length);
      appendThinkBlock(thinkSoFar, { isStreaming: true });
      // Stop here; the rest of the block will arrive in future chunks
      break;
    }

    // NORMAL CASE: fully closed <think>...</think> block
    const thinkText = content.slice(
      start + THINK_OPEN.length,
      closeStart
    );
    appendThinkBlock(thinkText, { isStreaming: false });

    // Continue scanning after the closing </think> tag
    index = closeStart + THINK_CLOSE.length;
  }

  // Fallback: if nothing was rendered, just show the raw content
  if (!container.childNodes.length) {
    appendTextBlock(content);
  }
}


// ======= Final Function =======
/**
 * Initialize streaming chat behavior on the composer form.
 *
 * - Guards against double initialization using a data attribute
 * - Submits the form via fetch and streams the assistant response
 * - Renders optimistic user + assistant bubbles into #messages
 * - Handles <think> blocks as collapsible debug sections
 * - Manages full-doc progress UI for "Docs + Full" mode
 * - Disables composer controls during streaming and re-enables afterwards
 * - Refreshes the current conversation messages via HTMX when finished
 * - Transforms the Send button into a Stop button during streaming, with cancellation via AbortController
 */
export function initStreamingChat(root = document) {
  const form = root.querySelector("#composer-form");
  if (!form) return;

  // Avoid double initialization on the same form element.
  if (form.dataset.streamingInit === "1") return;
  form.dataset.streamingInit = "1";

  const textarea = form.querySelector("textarea[name='user_input']");
  const messagesEl = document.getElementById("messages");
  const sendBtn = form.querySelector("#composer-send-btn");

  // Streaming state + Current AbortController
  let abortController = null;
  let isStreaming = false;

  // Visual helpers for the Send/Stop button
  const setSendButtonIdle = () => {
    if (!sendBtn) return;
    const labelSend = sendBtn.dataset.labelSend || "Send";
    sendBtn.dataset.state = "idle";
    sendBtn.innerHTML = labelSend;
    sendBtn.classList.remove("bg-red-500", "hover:bg-red-600");
    sendBtn.classList.add("bg-cyan-500", "hover:bg-cyan-600");
  };

  const setSendButtonStreaming = () => {
    if (!sendBtn) return;
    const labelStop = sendBtn.dataset.labelStop || "Stop";
    sendBtn.dataset.state = "streaming";
    sendBtn.innerHTML = `■ ${labelStop}`;
    sendBtn.classList.remove("bg-cyan-500", "hover:bg-cyan-600");
    sendBtn.classList.add("bg-red-500", "hover:bg-red-600");
  };

  if (sendBtn) {
    setSendButtonIdle();

    // During streaming, clicking the button should cancel rather than resubmit.
    sendBtn.addEventListener("click", (e) => {
      if (!isStreaming) return; // In idle mode, normal behavior (submit via form)
      e.preventDefault();
      e.stopPropagation();
      if (abortController) {
        abortController.abort();
      }
    });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    // If already streaming, the submit is ignored (the click is handled by the button handler).
    if (isStreaming) return;

    const text = (textarea.value || "").trim();
    if (!text) return;

    // Base form fields (includes things like llm_tier, etc.).
    const fd = new FormData(form);

    // Mirror hx-include="#source-selection-summary": send additional inputs.
    document
      .querySelectorAll("#source-selection-summary [name]")
      .forEach((el) => {
        fd.append(el.name, el.value);
      });

    // Determine whether we are in "Docs + Full" mode (special progress behavior).
    const modePresetInput = form.querySelector("#mode-preset-input");
    const docModeInput = form.querySelector("#doc-mode-input");

    const modePreset = modePresetInput ? modePresetInput.value : "free";
    const docMode = docModeInput ? docModeInput.value : "rag";
    const isFullDocsMode = modePreset === "docs" && docMode === "full";

    // Disable all controls EXCEPT the send button (which becomes Stop)
    form
      .querySelectorAll("input, textarea, button")
      .forEach((el) => {
        if (el === sendBtn) return;
        el.disabled = true;
      });

    if (sendBtn) {
      sendBtn.disabled = false;
      setSendButtonStreaming();
    }

    isStreaming = true;
    abortController = new AbortController();

    // 1) Optimistic user bubble.
    messagesEl.insertAdjacentHTML("beforeend", userBubbleHtml(text));

    // 2) Assistant placeholder bubble with a streaming target.
    const msgId = "assistant-stream-" + Date.now();
    messagesEl.insertAdjacentHTML("beforeend", assistantBubbleHtml(msgId));
    const target = document.getElementById(msgId);

    // Ensure the latest message is visible.
    target.scrollIntoView({ behavior: "smooth", block: "end" });

    // Clear the composer.
    textarea.value = "";

    // Progress bar handling only for "Docs + Full" mode.
    if (isFullDocsMode) {
      resetFullDocProgress();
      setFullDocProgressVisible(true);
    } else {
      setFullDocProgressVisible(false);
    }

    // 3) Streaming request to the backend.
    let fullText = "";
    let leftover = ""; // Carries partial progress segments across chunks.

    try {
      const response = await fetch("/message", {
        method: "POST",
        body: fd,
        signal: abortController.signal,
      });

      if (!response.ok || !response.body) {
        target.textContent = "[Error: Unable to start streaming]";
      } else {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          if (!chunk) continue;

          if (isFullDocsMode) {
            // Docs + Full mode: handle mixed PROGRESS events + final text.
            let textChunk = leftover + chunk;
            const segments = textChunk.split(PROGRESS_DELIM);
            leftover = segments.pop() || "";

            for (const segment of segments) {
              if (!segment) continue;

              if (segment.startsWith("__PROGRESS__:")) {
                // Progress event: "__PROGRESS__:done:total"
                const parts = segment.split(":");
                const doneBatches = parseInt(parts[1] || "0", 10);
                const totalBatches = parseInt(parts[2] || "0", 10);
                updateFullDocProgress(doneBatches, totalBatches);
              } else {
                // Final answer text (headings + merged answers).
                // We intentionally keep the progress bar visible while the
                // full-document analysis is ongoing; it will be hidden once
                // the whole stream finishes (see finally block).
                fullText += segment;
                renderWithThink(fullText, target);
                target.scrollIntoView({ behavior: "smooth", block: "end" });
              }
            }
          } else {
            // All other modes: simple streaming of plain text.
            fullText += chunk;
            renderWithThink(fullText, target);
            target.scrollIntoView({ behavior: "smooth", block: "end" });
          }
        }

        // Handle any trailing segment after the stream ends (Docs + Full only).
        if (isFullDocsMode && leftover) {
          if (leftover.startsWith("__PROGRESS__:")) {
            const parts = leftover.split(":");
            const doneBatches = parseInt(parts[1] || "0", 10);
            const totalBatches = parseInt(parts[2] || "0", 10);
            updateFullDocProgress(doneBatches, totalBatches);
          } else {
            fullText += leftover;
            renderWithThink(fullText, target);
          }
        }
      }
    } catch (err) {
      // Cancellation vs. true network error
      if (err.name === "AbortError") {
        // Optional: you can display a message in the speech bubble if you want
        // fullText += "\n\n[⏹ Generation canceled]";
        // renderWithThink(fullText, target);
      } else {
        console.error(err);
        target.textContent = "[Network error during streaming]";
      }
    } finally {
      isStreaming = false;
      abortController = null;

      // Reactivate all controls
      form
        .querySelectorAll("input, textarea, button")
        .forEach((el) => (el.disabled = false));

      if (sendBtn) {
        setSendButtonIdle();
      }

      textarea.focus();

      // In Docs + Full mode, ensure the progress bar is hidden once streaming is done.
      if (isFullDocsMode) {
        setFullDocProgressVisible(false);
      }

      // Refresh messages from the current conversation stored in session (if HTMX is present).
      if (window.htmx) {
        window.htmx.ajax(
          "GET",
          "/conversations/current/messages",
          "#messages"
        );
      }
    }
  });
}

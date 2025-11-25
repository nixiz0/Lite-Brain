import { formatLocal } from "./timestamps.js";

const SELECTOR = '#composer-bar textarea[name="user_input"][data-autoresize="true"]';
const MAX_HEIGHT = 160; // ~5 lines max before scrolling


// ======= Helpers Functions =======
/**
 * Auto-resize a textarea up to MAX_HEIGHT and toggle vertical scroll when needed.
 */
function autoresize(ta) {
  ta.style.height = "auto";
  const newHeight = Math.min(ta.scrollHeight, MAX_HEIGHT);
  ta.style.height = newHeight + "px";

  if (ta.scrollHeight > MAX_HEIGHT) {
    ta.style.overflowY = "auto";
  } else {
    ta.style.overflowY = "hidden";
  }
}

/**
 * Append an "optimistic" user message bubble to the messages list.
 * - Renders the text as a right-aligned bubble with avatar
 * - Adds a timestamp formatted via `formatLocal`
 * - Scrolls to the bottom sentinel if present
 */
function appendUserMessageBubble(text) {
  const msgs = document.getElementById("messages");
  if (!msgs) return;

  const row = document.createElement("div");
  row.className = "flex items-start gap-3 justify-end";

  const bubble = document.createElement("div");
  bubble.className =
    "max-w-[75ch] md:max-w-[85ch] " +
    "bg-slate-900/70 border border-slate-800 rounded-2xl px-4 py-3 shadow-sm ml-auto " +
    "prose prose-invert prose-headings:font-semibold prose-pre:shadow-inner prose-img:rounded-xl " +
    "prose-a:text-cyan-400 hover:prose-a:text-cyan-300";

  const content = document.createElement("div");
  content.textContent = text;
  bubble.appendChild(content);

  const now = new Date();
  const iso = now.toISOString();

  const timeEl = document.createElement("time");
  timeEl.className =
    "msg-timestamp text-xs text-slate-500 mt-2 block text-right";
  timeEl.setAttribute("datetime", iso);

  // Use the same local timestamp formatting as the rest of the app
  timeEl.textContent = formatLocal(iso);

  bubble.appendChild(timeEl);

  const avatar = document.createElement("div");
  avatar.className =
    "w-8 h-8 rounded-full bg-slate-700 text-white grid place-content-center";
  avatar.textContent = "U";

  row.appendChild(bubble);
  row.appendChild(avatar);
  msgs.appendChild(row);

  const sentinel = document.getElementById("bottom-sentinel");
  if (sentinel) {
    sentinel.scrollIntoView({ behavior: "smooth" });
  }
}


// ======= Final Function =======
/**
 * Initialize the chat prompt input behavior.
 *
 * - Auto-resizes the textarea on load and on input
 * - Handles Enter to submit / Shift+Enter for newline
 * - Sends optimistic user bubbles before HTMX requests
 * - Recalibrates textarea height after HTMX responses and swaps
 */
export function initPromptInput() {
  // Resize any existing prompt inputs on load
  document.querySelectorAll(SELECTOR).forEach(autoresize);

  // Auto-resize on input (event delegation)
  document.addEventListener(
    "input",
    (e) => {
      const ta = e.target.closest(SELECTOR);
      if (!ta) return;
      autoresize(ta);
    },
    { capture: true }
  );

  // Enter = submit, Shift+Enter = newline
  document.addEventListener("keydown", (e) => {
    const ta = e.target.closest(SELECTOR);
    if (!ta) return;

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const form = ta.closest("form");
      if (form) form.requestSubmit();
    }
  });

  // HTMX: before sending request -> optimistic message + clear input
  document.body.addEventListener("htmx:beforeRequest", (e) => {
    const detail = e.detail || {};
    const elt = detail.elt;
    if (!elt || elt.id !== "composer-form") return;

    const ta = elt.querySelector('textarea[name="user_input"]');
    if (!ta) return;

    const text = ta.value.trim();
    if (!text) {
      // Cancel HTMX request when input is empty
      e.preventDefault();
      return;
    }

    // 1) Show user bubble immediately (optimistic UI)
    appendUserMessageBubble(text);

    // 2) Clear textarea and re-apply autoresize
    ta.value = "";
    autoresize(ta);
  });

  // HTMX: after response -> ensure textarea height is recalculated
  document.body.addEventListener("htmx:afterRequest", (e) => {
    const detail = e.detail || {};
    const elt = detail.elt;
    if (!elt || elt.id !== "composer-form") return;

    const ta = elt.querySelector('textarea[name="user_input"]');
    if (ta) {
      autoresize(ta);
    }
  });

  // After HTMX swaps `#messages` (e.g. full conversation reload), recalibrate input
  document.body.addEventListener("htmx:afterSwap", (e) => {
    if (e.target && e.target.id === "messages") {
      const ta = document.querySelector(SELECTOR);
      if (ta) autoresize(ta);
    }
  });
}

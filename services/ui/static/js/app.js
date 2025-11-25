import { initLlmBootstrap }        from "./modules/llm-bootstrap.js";

import { initSidebar }        from "./modules/layout/sidebar.js";
import { initAutoScroll }     from "./modules/layout/scroll.js";

import { initConversations }  from "./modules/chat/conversations.js";
import { initTimestamps }     from "./modules/chat/timestamps.js";
import { initPromptInput }    from "./modules/chat/prompt-input.js";
import { initModelSelector }  from "./modules/chat/model-selector.js";
import { initModePresets } from "./modules/chat/mode-presets.js";
import { initSourceSelector } from "./modules/chat/source-selector.js";
import { initStreamingChat }  from "./modules/chat/streaming-chat.js";

import { initDropzone }       from "./modules/ui/dropzone.js";
import { initCodeBlocks }     from "./modules/ui/codeblocks.js";


// ----- Local DOM helpers (scoped to this file) -----
const qs  = (sel, root = document) => root.querySelector(sel);
const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

// Small utility to add/remove listeners, returns an unsubscribe function
const on  = (target, type, handler, opts) =>
  (target.addEventListener(type, handler, opts),
   () => target.removeEventListener(type, handler, opts));

const isDesktop = () => window.matchMedia("(min-width: 768px)").matches;  // Simple breakpoint helper


// Expose helpers for debugging from the browser console (optional)
window.__appDom = { qs, qsa, on, isDesktop };

window.addEventListener("DOMContentLoaded", () => {
  // -------- LLMs Installation ----------
  initLlmBootstrap();

  // -------- Layout ----------
  initSidebar();          // Sidebar behavior (mobile / desktop)
  initAutoScroll();       // Keep chat scrolled to the latest message

  // -------- Chat ------------
  initConversations();    // Conversation list interactions (e.g. rename via HTMX)
  initTimestamps();       // Localized timestamp rendering
  initPromptInput();      // Prompt textarea (auto-resize + submit on Enter)
  initModelSelector();    // Display currently selected model per conversation
  initModePresets();      // Display preset mode on a bar
  initStreamingChat();    // Live streaming of assistant responses

  // -------- UI --------------
  initDropzone();         // File dropzone in the modal (if present)
  initCodeBlocks();       // Enhance code blocks (syntax / controls)
});

// Re-run initializers when HTMX swaps parts of the DOM
document.body.addEventListener("htmx:afterSwap", (e) => {
  const target = e.target;
  if (!target) return;

  if (target.id === "modal-area") {
    // Modal content has been replaced: re-init dropzone + source selector
    initDropzone(target);
    initSourceSelector(target);
  }

  if (target.id === "sidebar-conversations") {
    // Sidebar conversations updated: re-bind conversation handlers + timestamps
    initConversations(target);
    initTimestamps(target);
  }

  if (target.id === "messages") {
    // Messages area updated: refresh message timestamps
    initTimestamps(target);
  }

  // If the swapped fragment contains the pattern selector, the listeners are reattached to it
  if (target.id === "model-selector" || target.querySelector("#model-selector")) {
    initModelSelector();
  }
});

// Custom event to close the modal from anywhere
document.body.addEventListener("close-modal", () => {
  const modalArea = document.getElementById("modal-area");
  if (modalArea) {
    modalArea.innerHTML = "";  // Clear modal content
  }
});

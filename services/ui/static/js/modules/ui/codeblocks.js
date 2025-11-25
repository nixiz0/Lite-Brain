let listenersAttached = false;

// Small helper to create consistently styled action buttons
function btn(label) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = label;
  b.className = "px-2 py-1 text-xs rounded bg-slate-700 hover:bg-slate-600";
  return b;
}

/**
 * Enhance <pre> code blocks within the #messages area:
 * - wrap them into a "code-card" container
 * - add "Copy" and "Wrap/No-wrap" controls
 */
export function enhanceCodes(root = document) {
  // Restrict enhancement to the messages section if present
  const scope =
    root.querySelector?.("#messages") ||
    document.getElementById("messages") ||
    document;

  scope.querySelectorAll("pre").forEach((pre) => {
    // Avoid re-processing already enhanced blocks
    if (pre.dataset.enhanced) return;
    pre.dataset.enhanced = "1";

    // Wrapper container for the code block and its actions
    const wrapper = document.createElement("div");
    wrapper.className = "code-card"; // CSS styles expected in base.html
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(pre);

    // Actions container (top-right utilities bar, etc.)
    const actions = document.createElement("div");
    actions.className = "code-actions";

    // --- Copy-to-clipboard button ---
    const copyBtn = btn("Copy");
    copyBtn.addEventListener("click", async () => {
      await navigator.clipboard.writeText(pre.innerText);
      const old = copyBtn.textContent;
      copyBtn.textContent = "Copied !";
      setTimeout(() => (copyBtn.textContent = old), 1200);
    });

    // --- Wrap / No-wrap toggle button ---
    const wrapBtn = btn("Wrap");
    let wrapped = false;
    wrapBtn.addEventListener("click", () => {
      wrapped = !wrapped;
      pre.style.whiteSpace = wrapped ? "pre-wrap" : "pre";
      pre.style.wordBreak = wrapped ? "break-word" : "normal";
      wrapBtn.textContent = wrapped ? "No-wrap" : "Wrap";
    });

    actions.append(copyBtn, wrapBtn);
    wrapper.appendChild(actions);

    // Notify listeners (if any) that code blocks have just been enhanced
    document.dispatchEvent(new CustomEvent("codeblocks:enhanced"));
  });
}


/**
 * Attach initializers and listeners so that newly injected code blocks
 * (HTMX swaps, DOM mutations) are also enhanced.
 */
export function initCodeBlocks() {
  // Ensure we only register listeners once
  if (listenersAttached) return;
  listenersAttached = true;

  // 1) Run once on initial page load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => enhanceCodes());
  } else {
    enhanceCodes();
  }

  // 2) Re-run enhancement after HTMX swaps affecting #messages
  document.body.addEventListener("htmx:afterSwap", (e) => {
    const t = e?.target || e?.detail?.target;
    if (!t) return;
    if (t.id === "messages" || t.querySelector?.("#messages")) {
      enhanceCodes(t);
    }
  });

  // 3) Fallback: observe direct DOM mutations under #messages
  const messages = document.getElementById("messages");
  if (messages && "MutationObserver" in window) {
    const mo = new MutationObserver(() => enhanceCodes(messages));
    mo.observe(messages, { childList: true, subtree: true });
  }
}

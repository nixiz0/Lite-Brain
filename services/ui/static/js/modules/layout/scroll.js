// Auto-scroll state flags
const NEAR_BOTTOM_PX = 160;   // threshold below which we consider the user "near bottom"
let autoScrollPaused = false; // paused while user is typing (textarea focused)
let justSentMessage  = false; // one-shot flag set when a /message form is submitted


// ======= Helpers Functions =======
/**
 * Find the closest scrollable ancestor of a given element on the Y axis.
 */
function findScrollingAncestor(el) {
  let cur = el?.parentElement || null;
  while (cur) {
    const cs = getComputedStyle(cur);
    const canScrollY = /(auto|scroll)/.test(cs.overflowY);
    if (canScrollY && cur.scrollHeight > cur.clientHeight + 1) return cur;
    cur = cur.parentElement;
  }
  return null;
}

/**
 * Sentinel element used as the scroll target for "go to bottom".
 */
function getSentinel() {
  return document.getElementById("bottom-sentinel");
}

/**
 * Determine which element should be treated as the main vertical scroller:
 * - the scrollable ancestor of the sentinel
 * - or #content if it scrolls
 * - or the document itself as fallback
 */
function getScroller() {
  const sentinel = getSentinel();
  const byAncestor = sentinel ? findScrollingAncestor(sentinel) : null;
  const content = document.getElementById("content");
  if (byAncestor) return byAncestor;
  if (content && content.scrollHeight > content.clientHeight + 1) return content;
  return document.scrollingElement || document.documentElement;
}

/**
 * Distance (in px) from the bottom of the scrollable area.
 */
function distanceToBottom(el) {
  const s = el || getScroller();
  return s.scrollHeight - s.scrollTop - s.clientHeight;
}

/**
 * Returns true if the user is considered "near" the bottom of the scroller.
 */
function isNearBottom() {
  return distanceToBottom(getScroller()) <= NEAR_BOTTOM_PX;
}

/**
 * Ensure the bottom padding mirrors the height of the composer bar so
 * the last message is not hidden behind it and scroll-padding works.
 */
function syncBottomPadding() {
  const bar = document.getElementById("composer-bar");
  const sentinel = getSentinel();
  const scroller = getScroller();
  if (!bar || !sentinel || !scroller) return;

  const h = bar.getBoundingClientRect().height || 0;
  const extra = 12;
  const padVal = `${h + extra}px`;

  // If the scroller is a dedicated element, pad that element
  if (scroller !== document.scrollingElement && scroller !== document.documentElement) {
    scroller.style.paddingBottom = padVal;
    scroller.style.scrollPaddingBottom = padVal;
  } else {
    // Scroller is the page → pad the wrapper (parent of the sentinel) and set scroll-padding on <html>
    const wrapper = sentinel.parentElement;
    if (wrapper) wrapper.style.paddingBottom = padVal;
    document.documentElement.style.scrollPaddingBottom = padVal;
  }
}

/**
 * Scroll to the bottom sentinel (smooth or instant).
 */
function scrollToBottom({ smooth = true } = {}) {
  const sentinel = getSentinel();
  if (!sentinel) return;
  sentinel.scrollIntoView({
    block: "end",
    inline: "nearest",
    behavior: smooth ? "smooth" : "auto",
  });
}

/**
 * Auto-scroll to bottom if allowed (user is near bottom and not typing),
 * unless `force` is true.
 *
 * Uses multiple passes to handle late reflows (images, fonts, code enhancers).
 */
function resilientScrollBottom({ force = false } = {}) {
  if (!force) {
    if (autoScrollPaused || !isNearBottom()) return;
  }
  syncBottomPadding();

  // Multiple passes to stabilize scroll after layout changes
  requestAnimationFrame(() => {
    scrollToBottom({ smooth: true });
    setTimeout(() => {
      if (distanceToBottom() > 24) scrollToBottom({ smooth: false });
      setTimeout(() => {
        if (distanceToBottom() > 24) scrollToBottom({ smooth: false });
      }, 250);
    }, 120);
  });
}


// ======= Final Function =======
/**
 * Initialize chat auto-scroll behavior:
 * - scroll to bottom on initial load / conversation change
 * - integrate with HTMX swaps
 * - respond to images loading, code enhancement, and composer resize
 * - pause when user is typing, resume when done
 */
export function initAutoScroll() {
  // Initial scroll (first server render or first conversation load)
  resilientScrollBottom({ force: true });

  // --- HTMX: mark that a message form is being submitted ---
  document.body.addEventListener("htmx:beforeRequest", (e) => {
    const elt = e?.target || e?.detail?.target;
    if (
      elt &&
      (elt.matches?.('form[action="/message"]') ||
        elt.matches?.('form[hx-post="/message"]'))
    ) {
      justSentMessage = true;
    }
  });

  // --- HTMX: after swap, decide if we should force auto-scroll ---
  document.body.addEventListener("htmx:afterSwap", (e) => {
    const t = e?.target || e?.detail?.target;
    const sentinel = getSentinel();

    const touchesContent =
      !!t &&
      (t.id === "content" ||
        t.closest?.("#content") ||
        (sentinel && (t === sentinel || t.contains?.(sentinel))));

    const isMessagesSwap =
      !!t && (t.id === "messages" || t.querySelector?.("#messages"));
    const force = !!justSentMessage || touchesContent;

    if (isMessagesSwap || touchesContent) {
      // Let the layout settle before scrolling
      requestAnimationFrame(() =>
        setTimeout(() => resilientScrollBottom({ force }), 0),
      );
      justSentMessage = false; // one-shot flag
    }
  });

  // --- MutationObserver: detect conversation load (bottom sentinel appears) ---
  const content = document.getElementById("content");
  if (content) {
    const mo = new MutationObserver((mutations) => {
      for (const m of mutations) {
        const added = [...m.addedNodes].some(
          (n) =>
            n.nodeType === 1 &&
            (n.id === "bottom-sentinel" ||
              n.querySelector?.("#bottom-sentinel")),
        );
        if (added) {
          requestAnimationFrame(() =>
            resilientScrollBottom({ force: true }),
          );
          break;
        }
      }
    });
    mo.observe(content, { childList: true, subtree: true });
  }

  // Images finishing loading → try to re-scroll if user is near bottom and not typing
  document.body.addEventListener(
    "load",
    (ev) => {
      if (ev.target?.tagName === "IMG") resilientScrollBottom();
    },
    true,
  );

  // Code blocks enhancer (height may change significantly)
  document.addEventListener("codeblocks:enhanced", () =>
    resilientScrollBottom(),
  );

  // Composer bar resize (textarea auto-resize etc.)
  const bar = document.getElementById("composer-bar");
  if (bar && "ResizeObserver" in window) {
    const ro = new ResizeObserver(() => resilientScrollBottom());
    ro.observe(bar);
  }

  // Window resize can change available height
  window.addEventListener("resize", () => resilientScrollBottom());

  // User typing: pause auto-scroll while the textarea is focused
  const ta = document.querySelector('#composer-bar textarea[name="user_input"]');
  if (ta) {
    ta.addEventListener("focusin", () => {
      autoScrollPaused = true;
    });
    ta.addEventListener("focusout", () => {
      autoScrollPaused = false;
      resilientScrollBottom();
    });
    // We intentionally do not scroll on each input event to avoid disrupting typing.
  }

  // Optional hook for a “scroll to bottom” indicator:
  // we rely on isNearBottom() inside resilientScrollBottom(),
  // but this listener can be used to toggle UI hints.
  const scroller = getScroller();
  scroller.addEventListener(
    "scroll",
    () => {
      // No auto-scroll here: resilientScrollBottom() already guards on isNearBottom().
      // This is a good place to toggle a "Go to bottom" button if !isNearBottom().
    },
    { passive: true },
  );
}

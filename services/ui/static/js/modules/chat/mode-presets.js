import { setCookie, getCookie } from "../cookie.js";

/**
 * Initialize mode preset UI.
 * - Restores active mode from cookie, then server, then defaults to "free".
 * - Manages active pill styles, label/description, and responsive layout.
 * - Handles "More" modal and collapse/expand toggle.
 *
 * @param {Document | HTMLElement} [root=document] - DOM root to scope the search.
 */
export function initModePresets(root = document) {
  const bar = root.querySelector("#mode-bar");
  if (!bar) return;

  const pills = Array.from(bar.querySelectorAll(".mode-pill"));
  if (!pills.length) return;

  const pillsContainer = document.getElementById("mode-pills");
  const hiddenInput = document.getElementById("mode-preset-input");
  const activeLabel = document.getElementById("mode-active-label");
  const descriptionEl = document.getElementById("mode-description");

  const moreBtn = document.getElementById("mode-more-btn");
  const moreModal = document.getElementById("mode-more-modal");
  const panel = document.getElementById("mode-more-panel");
  const moreList = document.getElementById("mode-more-list");

  // Docs sub-mode elements
  const docsOptions = document.getElementById("docs-options");
  const docModeInput = document.getElementById("doc-mode-input");
  const docModeButtons = docsOptions
    ? Array.from(docsOptions.querySelectorAll(".doc-mode-pill"))
    : [];

  const COOKIE_NAME = "modePreset";

  // Initial value from server (e.g. form default)
  const currentFromServer = hiddenInput?.value || "free";

  // Try restoring from cookie
  const modeFromCookie = getCookie(COOKIE_NAME);

  // Priority: cookie > server > "free"
  const initialMode = modeFromCookie || currentFromServer || "free";

  const ACTIVE_CLASSES = ["border-cyan-500", "text-cyan-100", "shadow-sm"];
  const INACTIVE_CLASSES = ["border-slate-700", "text-slate-300"];

  const DOC_ACTIVE_CLASSES = [
    "border-cyan-500",
    "bg-slate-900/70",
    "text-slate-100",
  ];
  const DOC_INACTIVE_CLASSES = [
    "border-slate-700",
    "bg-slate-900/40",
    "text-slate-300",
  ];

  /**
   * Set doc sub-mode (rag / full) for Docs preset.
   */
  function setDocMode(mode) {
    if (!docModeInput || !docModeButtons.length) return;

    const targetMode = mode || "rag";
    docModeInput.value = targetMode;

    docModeButtons.forEach((btn) => {
      const isActive = btn.dataset.docMode === targetMode;

      DOC_INACTIVE_CLASSES.forEach((cls) => btn.classList.add(cls));
      DOC_ACTIVE_CLASSES.forEach((cls) => btn.classList.remove(cls));

      if (isActive) {
        DOC_ACTIVE_CLASSES.forEach((cls) => btn.classList.add(cls));
        DOC_INACTIVE_CLASSES.forEach((cls) => btn.classList.remove(cls));
      }
    });
  }

  /**
   * Set the active mode:
   * - Update pill styles.
   * - Sync hidden form input.
   * - Persist preference in cookie.
   * - Update label and description.
   * - Show/hide Docs sub-options.
   */
  function setActive(mode) {
    pills.forEach((btn) => {
      const isActive = btn.dataset.mode === mode;

      INACTIVE_CLASSES.forEach((cls) => btn.classList.add(cls));
      ACTIVE_CLASSES.forEach((cls) => btn.classList.remove(cls));

      if (isActive) {
        ACTIVE_CLASSES.forEach((cls) => btn.classList.add(cls));
        INACTIVE_CLASSES.forEach((cls) => btn.classList.remove(cls));
      }
    });

    const activeBtn = pills.find((b) => b.dataset.mode === mode) || pills[0];
    if (!activeBtn) return;

    const activeMode = activeBtn.dataset.mode;

    if (hiddenInput) {
      hiddenInput.value = activeMode;
    }

    // Show/hide docs sub-options depending on active mode
    if (docsOptions) {
      if (activeMode === "docs") {
        docsOptions.classList.remove("hidden");
      } else {
        docsOptions.classList.add("hidden");
      }
    }

    // Persist preference for 1 year
    setCookie(COOKIE_NAME, activeMode, 365);

    if (activeLabel) {
      activeLabel.textContent = activeBtn.dataset.label || "Free mode";
    }
    if (descriptionEl) {
      descriptionEl.textContent =
        activeBtn.dataset.description || "...";
    }
  }

  /**
   * Return max number of visible pills based on viewport width.
   */
  function getMaxVisible() {
    if (window.matchMedia("(min-width: 1450px)").matches) {
      return 9; // desktop
    }
    if (window.matchMedia("(min-width: 1024px)").matches) {
      return 7; // desktop
    }
    if (window.matchMedia("(min-width: 768px)").matches) {
      return 5; // tablet
    }
    return 4;   // mobile
  }

  /**
   * Show only the first N pills (based on getMaxVisible).
   * Toggle visibility of the "More" button accordingly.
   */
  function updateVisiblePills() {
    const maxVisible = getMaxVisible();
    let hiddenCount = 0;

    pills.forEach((btn, index) => {
      if (index < maxVisible) {
        btn.classList.remove("hidden");
      } else {
        btn.classList.add("hidden");
        hiddenCount++;
      }
    });

    if (moreBtn) {
      if (hiddenCount > 0) {
        moreBtn.classList.remove("hidden");
      } else {
        moreBtn.classList.add("hidden");
      }
    }
  }

  /**
   * Open the "More" modal:
   * - Clone all currently hidden pills into the modal list.
   * - Each clone delegates selection back to its original pill.
   */
  function openMoreModal() {
    if (!moreModal || !moreList) return;

    moreList.innerHTML = "";

    pills
      .filter((btn) => btn.classList.contains("hidden"))
      .forEach((btn) => {
        const clone = btn.cloneNode(true);

        // Clones must be visible inside the modal
        clone.classList.remove("hidden");

        clone.addEventListener("click", () => {
          btn.click();      // trigger original button selection
          closeMoreModal(); // close modal after selection
        });

        moreList.appendChild(clone);
      });

    moreModal.classList.remove("hidden");
    moreModal.classList.add("flex");
  }

  /**
   * Close the "More" modal.
   */
  function closeMoreModal() {
    if (!moreModal) return;
    moreModal.classList.add("hidden");
    moreModal.classList.remove("flex");
  }

  if (moreBtn) {
    moreBtn.addEventListener("click", openMoreModal);
  }

  if (moreModal) {
    moreModal.querySelectorAll("[data-modal-close]").forEach((el) => {
      el.addEventListener("click", closeMoreModal);
    });
  }

  // Close the modal if you click outside the panel
  document.addEventListener("click", (event) => {
    if (!moreModal) return;

    // If the modal is closed, nothing happens.
    const isHidden = moreModal.classList.contains("hidden");
    if (isHidden) return;

    // Clicking inside the panel or on the "more" button does not close it.
    if (panel?.contains(event.target) || moreBtn?.contains(event.target)) {
      return;
    }

    // Otherwise: click outside → close
    closeMoreModal();
  });

  // Initialize selection from cookie/server/default
  setActive(initialMode);

  // Initialize doc sub-mode UI (default "rag")
  if (docModeInput && docModeButtons.length) {
    const initialDocMode = docModeInput.value || "rag";
    setDocMode(initialDocMode);

    docModeButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.dataset.docMode || "rag";
        setDocMode(mode);
      });
    });
  }

  // Attach click handlers on pills
  pills.forEach((btn) => {
    btn.addEventListener("click", () => {
      setActive(btn.dataset.mode);
    });
  });

  // --- Collapse/expand bar toggle ---
  const toggleBtn = document.getElementById("mode-toggle-btn");
  const toggleIcon = document.getElementById("mode-toggle-icon");
  let isOpen = true;

  /**
   * Toggle the visibility of the mode bar and sync toggle UI state.
   */
  function setOpen(open) {
    isOpen = open;

    if (open) {
      bar.classList.remove("hidden");
    } else {
      bar.classList.add("hidden");
    }

    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
    }

    if (toggleIcon) {
      toggleIcon.classList.toggle("rotate-180", !open);
    }
  }

  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      setOpen(!isOpen);
    });
  }

  // Default: bar is open
  setOpen(true);

  // Initialize responsive layout and keep it in sync on resize
  updateVisiblePills();
  window.addEventListener("resize", updateVisiblePills);
}

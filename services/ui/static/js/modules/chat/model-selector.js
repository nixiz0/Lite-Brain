/**
 * Initialize the LLM model selector UI.
 *
 * - Syncs visible radio buttons with a hidden `<input id="llm-tier-input">`
 * - Applies active styling to the selected model option
 * - Persists the selection by POSTing to `/conversations/current/llm-tier`
 * - Reacts to HTMX `set-llm-tier` events to update the selection from the backend
 */
export function initModelSelector(root = document) {
  const selector = root.querySelector("#model-selector");
  const hiddenInput = document.getElementById("llm-tier-input");
  if (!selector || !hiddenInput) return;

  const labels = Array.from(selector.querySelectorAll("label"));

  /**
   * Apply visual and form state for a given tier value.
   * Keeps all radio inputs and label styles in sync with the active tier.
   */
  const applySelection = (tierValue) => {
    labels.forEach((label) => {
      const input = label.querySelector('input[name="llm_tier"]');
      if (!input) return;

      const isActive = input.value === tierValue;

      // Keep radio checked state aligned with the selected tier
      input.checked = isActive;

      // Toggle active styles for the selected label
      label.classList.toggle("ring-1", isActive);
      label.classList.toggle("ring-cyan-500", isActive);
      label.classList.toggle("border-cyan-500", isActive);
      label.classList.toggle("bg-slate-800/70", isActive);
    });
  };

  // 1) Initialize from server-side value (hidden input or pre-checked radio)
  let initialValue = hiddenInput.value;
  if (!initialValue) {
    const checkedInput = selector.querySelector(
      'input[name="llm_tier"]:checked'
    );
    if (checkedInput) {
      initialValue = checkedInput.value;
    }
  }
  if (initialValue) {
    applySelection(initialValue);
  }

  // 2) When the user changes the selected tier via the UI
  selector.addEventListener("change", (e) => {
    const target = e.target;
    if (!target || target.name !== "llm_tier") return;

    const value = target.value;

    // Mirror selection into hidden input for form / server usage
    hiddenInput.value = value;
    applySelection(value);

    // Persist the new tier on the current conversation
    fetch("/conversations/current/llm-tier", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: new URLSearchParams({ llm_tier: value }),
    }).catch((err) => {
      console.error("Update error llm tier:", err);
    });
  });

  // 3) When backend triggers an HTMX custom event: { "set-llm-tier": "turbo" }
  document.body.addEventListener("set-llm-tier", (event) => {
    // HTMX puts the payload value in event.detail
    const tier = event.detail?.value ?? event.detail;
    if (!tier) return;

    hiddenInput.value = tier;
    applySelection(tier);
  });
}

import { t } from "./i18n-frontend.js";

export function initLlmBootstrap() {
  const overlay         = document.getElementById("llm-bootstrap-overlay");
  const messageEl       = document.getElementById("llm-bootstrap-message");
  const modelLabelEl    = document.getElementById("llm-bootstrap-model-label");
  const progressLabelEl = document.getElementById("llm-bootstrap-progress-label");
  const progressBarEl   = document.getElementById("llm-bootstrap-progress-bar");

  // If the overlay is not present, there's nothing to bootstrap.
  if (!overlay) return;

  /**
   * Poll backend for LLM bootstrap status and update the overlay UI.
   *
   * - Hides the overlay when status === "ready"
   * - Updates message, current model label, and progress bar
   * - Uses a longer retry delay on errors
   */
  async function pollStatus() {
    try {
      const res = await fetch("/llm/bootstrap-status", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);

      const data          = await res.json();
      const status        = data.status;
      const currentModel  = data.current_model || null;
      const progress      = typeof data.progress === "number" ? data.progress : 0;
      const message       = data.message || "";

      // LLM is ready → hide overlay and stop polling.
      if (status === "ready") {
        overlay.classList.add("hidden");
        return;
      }

      // Show overlay while the server is still bootstrapping or errored.
      overlay.classList.remove("hidden");

      if (messageEl && message) {
        messageEl.textContent = message;
      }

      if (modelLabelEl) {
        modelLabelEl.textContent = currentModel || t("js_llm_preparing_models");
      }

      if (progressBarEl && progressLabelEl) {
        const clamped = Math.max(0, Math.min(100, progress));
        progressBarEl.style.width   = clamped + "%";
        progressLabelEl.textContent = clamped.toFixed(0) + "%";
      }

      // On errors, slow down polling a bit to avoid hammering the backend.
      const delay = status === "error" ? 5000 : 1000;
      setTimeout(pollStatus, delay);
    } catch (err) {
      // Backend not reachable yet → show generic connection state and retry slowly.
      overlay.classList.remove("hidden");
      if (messageEl) {
        messageEl.textContent = t("js_llm_waiting_server");
      }
      if (modelLabelEl) {
        modelLabelEl.textContent = t("js_llm_connection");
      }
      setTimeout(pollStatus, 5000);
    }
  }

  // Start polling immediately; this is called after DOMContentLoaded.
  pollStatus();
}

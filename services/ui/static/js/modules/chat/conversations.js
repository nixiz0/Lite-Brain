let convHandlersBound = false;   // Prevent registering global listeners more than once
let draggingConvId = null;       // Id of the conversation currently being dragged
let draggingRow = null;          // DOM element of the row currently being dragged


/**
 * Initialize conversations UI interactions.
 *
 * - Marks `.conv-row` elements as draggable within the provided root
 * - Registers global double-click / drag-and-drop handlers (only once)
 * - Handles dropping conversations into folders and updates UI via AJAX/HTMX
 */
export function initConversations(root = document) {
  // Mark all conversation rows in the given root as draggable
  root.querySelectorAll(".conv-row").forEach((row) => {
    row.setAttribute("draggable", "true");
  });

  // Global handlers are installed only once
  if (convHandlersBound) return;
  convHandlersBound = true;

  // Global double-click handler to trigger inline rename via HTMX
  document.addEventListener(
    "dblclick",
    (e) => {
      const row = e.target.closest(".conv-row");
      if (!row) return;

      e.preventDefault();
      e.stopPropagation();

      const url = row.getAttribute("data-edit-url");
      if (!url) return;

      if (window.htmx) {
        window.htmx.ajax("GET", url, {
          target: "#" + row.id,
          swap: "innerHTML",
        });
      }
    },
    { capture: true }
  );

  // Start dragging a conversation row
  document.addEventListener("dragstart", (e) => {
    const row = e.target.closest(".conv-row");
    if (!row) return;
    const convId = row.dataset.convId;
    if (!convId) return;

    draggingConvId = convId;
    draggingRow = row;

    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", convId);
    }

    // Highlight dragged row
    row.classList.add(
      "bg-slate-900/80",
      "shadow-lg",
      "ring",
      "ring-cyan-500/60",
      "rounded-lg",
      "translate-x-1",
      "scale-[0.99]",
      "transition",
      "duration-150"
    );

    // Global cursor/selection tweaks during drag
    document.body.classList.add("cursor-grabbing", "select-none");
  });

  // End of drag: reset visual state
  document.addEventListener("dragend", () => {
    draggingConvId = null;

    if (draggingRow) {
      draggingRow.classList.remove(
        "bg-slate-900/80",
        "shadow-lg",
        "ring",
        "ring-cyan-500/60",
        "rounded-lg",
        "translate-x-1",
        "scale-[0.99]",
        "transition",
        "duration-150"
      );
      draggingRow = null;
    }

    document.body.classList.remove("cursor-grabbing", "select-none");

    // Clear drop-target styling on all folders
    document
      .querySelectorAll("[data-folder-id]")
      .forEach((el) =>
        el.classList.remove(
          "bg-slate-900/80",
          "ring",
          "ring-cyan-400",
          "shadow-md",
          "translate-x-[2px]"
        )
      );
  });

  // While dragging over a folder, mark it as a drop target
  document.addEventListener("dragover", (e) => {
    if (!draggingConvId) return;
    const folderEl = e.target.closest("[data-folder-id]");
    if (!folderEl) return;

    e.preventDefault(); // Allow drop
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = "move";
    }

    folderEl.classList.add(
      "bg-slate-900/80",
      "ring",
      "ring-cyan-400",
      "shadow-md",
      "translate-x-[2px]"
    );
  });

  // Leaving a folder: remove drop-target styling
  document.addEventListener("dragleave", (e) => {
    const folderEl = e.target.closest("[data-folder-id]");
    if (!folderEl) return;

    folderEl.classList.remove(
      "bg-slate-900/80",
      "ring",
      "ring-cyan-400",
      "shadow-md",
      "translate-x-[2px]"
    );
  });

  // Drop a conversation on a folder to import it
  document.addEventListener("drop", async (e) => {
    const folderEl = e.target.closest("[data-folder-id]");
    if (!folderEl || !draggingConvId) return;

    e.preventDefault();
    const folderId = folderEl.dataset.folderId;
    const convId =
      (e.dataTransfer && e.dataTransfer.getData("text/plain")) ||
      draggingConvId;

    if (!folderId || !convId) return;

    // Dim folder while the import request is in progress
    folderEl.classList.add("opacity-60");

    try {
      const resp = await fetch(
        `/folders/${folderId}/import-conversation/${convId}`,
        {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
          },
        }
      );

      const html = await resp.text();

      // If the folder modal is open, refresh its documents list
      const docsList = document.querySelector("#folder-documents-list");
      if (docsList) {
        docsList.innerHTML = html;
      }

      // Ask HTMX to refresh folder counts in the sidebar
      if (window.htmx) {
        window.htmx.trigger(document.body, "refresh-folders");
      }
    } catch (err) {
      console.error("Error importing conversation into folder:", err);
    } finally {
      folderEl.classList.remove(
        "opacity-60",
        "bg-slate-900/80",
        "ring",
        "ring-cyan-400",
        "shadow-md",
        "translate-x-[2px]"
      );

      if (draggingRow) {
        draggingRow.classList.remove(
          "bg-slate-900/80",
          "shadow-lg",
          "ring",
          "ring-cyan-500/60",
          "rounded-lg",
          "translate-x-1",
          "scale-[0.99]",
          "transition",
          "duration-150"
        );
        draggingRow = null;
      }

      document.body.classList.remove("cursor-grabbing", "select-none");
      draggingConvId = null;
    }
  });
}

/**
 * Initialize the source selector behavior.
 *
 * - When a folder checkbox is toggled, all document checkboxes belonging
 *   to that folder are automatically set to the same checked state.
 * - Works on any DOM root (useful after HTMX swaps).
 */
export function initSourceSelector(root = document) {
  const folderCheckboxes = root.querySelectorAll(
    'input[type="checkbox"][data-folder-checkbox="true"]'
  );

  folderCheckboxes.forEach((folderCb) => {
    folderCb.addEventListener("change", () => {
      const folderId = folderCb.dataset.folderId;
      if (!folderId) return;

      // Find all document checkboxes inside this folder
      const docCheckboxes = root.querySelectorAll(
        `input[type="checkbox"][data-doc-checkbox="true"][data-folder-id="${folderId}"]`
      );

      // Sync their checked state with the folder checkbox
      docCheckboxes.forEach((docCb) => {
        docCb.checked = folderCb.checked;
      });
    });
  });
}

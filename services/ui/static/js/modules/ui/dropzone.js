import { tf } from "../i18n-frontend.js";

/**
 * Initialize drag-and-drop file upload zones inside the given root element.
 *
 * Looks for:
 * - form[data-dropzone]
 * - a file input inside the form
 * - a drop area element with id starting with "dropzone-"
 * - optional [data-preview] list to show selected files
 * - optional [data-counter] element to show "current/max"
 */
export function initDropzone(root = document) {
  const forms = Array.from(root.querySelectorAll('form[data-dropzone]'));

  forms.forEach((form) => {
    const max = parseInt(form.getAttribute('data-max-files') || '5', 10);
    const input = form.querySelector('input[type="file"]');
    const dz = form.querySelector('[id^="dropzone-"]');
    const preview = form.querySelector('[data-preview]');
    const counter = form.querySelector('[data-counter]');

    // Nothing to wire if we don't have at least the file input + drop area
    if (!input || !dz) return;

    // Render the selected files into the preview list and update the counter
    const updatePreview = (files) => {
      if (!preview || !counter) return;

      preview.innerHTML = '';
      Array.from(files).forEach((f) => {
        const li = document.createElement('li');
        li.textContent = f.name;
        preview.appendChild(li);
      });
      counter.textContent = `${files.length}/${max}`;
    };

    // Apply max limit, assign files to the input, update preview, and submit via "change"
    const setFilesAndSubmit = (files) => {
      const list = new DataTransfer();

      if (files.length > max && preview) {
        // Inform the user that only the first `max` files are used
        const msg = tf("js_dropzone_only_first_files", { max });

        preview.innerHTML =
          `<li class="text-red-400">${msg}</li>` +
          preview.innerHTML;
      }

      // Limit to the first `max` files
      Array.from(files)
        .slice(0, max)
        .forEach((f) => list.items.add(f));

      input.files = list.files;
      updatePreview(input.files);

      // Fire a "change" event so HTMX (or other listeners) can submit the form
      input.dispatchEvent(new Event('change', { bubbles: true }));
    };

    // Click on the dropzone opens the native file selector
    dz.addEventListener('click', () => input.click());
    dz.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        input.click();
      }
    });

    // Drag & drop highlighting
    ['dragenter', 'dragover'].forEach((evt) =>
      dz.addEventListener(evt, (e) => {
        e.preventDefault();
        dz.classList.add('ring-2', 'ring-cyan-500', 'border-cyan-500');
      }),
    );

    // Remove highlighting when leaving or dropping
    ['dragleave', 'drop'].forEach((evt) =>
      dz.addEventListener(evt, (e) => {
        e.preventDefault();
        dz.classList.remove('ring-2', 'ring-cyan-500', 'border-cyan-500');
      }),
    );

    // Handle dropped files
    dz.addEventListener('drop', (e) => {
      const files = e.dataTransfer?.files || [];
      if (!files.length) return;
      setFilesAndSubmit(files);
    });

    // Handle files selected via the native file input
    input.addEventListener('change', () => {
      if (input.files?.length) {
        // Enforce the max limit on the front-end as well
        if (input.files.length > max) {
          const list = new DataTransfer();
          Array.from(input.files)
            .slice(0, max)
            .forEach((f) => list.items.add(f));
          input.files = list.files;
        }
        updatePreview(input.files);
      }
    });
  });
}

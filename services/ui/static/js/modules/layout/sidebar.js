// Simple breakpoint helper
const isDesktop = () => window.matchMedia("(min-width: 768px)").matches;

// ======= Helpers Functions =======
// ----- Overlay helpers (mobile backdrop) -----
function showOverlay(overlay) {
  overlay.classList.remove("hidden");
  // Let the browser apply "display" before starting the opacity transition
  requestAnimationFrame(() => overlay.classList.remove("opacity-0"));
}

function hideOverlay(overlay) {
  overlay.classList.add("opacity-0");
  overlay.addEventListener(
    "transitionend",
    () => overlay.classList.add("hidden"),
    { once: true },
  );
}

// ----- Sidebar behavior: mobile (off-canvas) -----
function openSidebarMobile(sidebar, overlay) {
  sidebar.classList.remove("-translate-x-full");
  showOverlay(overlay);
}

function closeSidebarMobile(sidebar, overlay) {
  sidebar.classList.add("-translate-x-full");
  hideOverlay(overlay);
}

// ----- Sidebar behavior: desktop (persistent column) -----
function showSidebarDesktop(sidebar, main, composer, desktopShowBtn, desktopHideBtn) {
  sidebar.classList.remove("md:-translate-x-full");
  sidebar.classList.add("md:translate-x-0");
  main.classList.add("md:ml-[280px]");      // reserve horizontal space for the sidebar
  composer.classList.add("md:left-[280px]"); // align composer with main content
  desktopShowBtn.classList.add("hidden");
  desktopHideBtn.classList.remove("hidden");
}

function hideSidebarDesktop(sidebar, main, composer, desktopShowBtn, desktopHideBtn) {
  sidebar.classList.remove("md:translate-x-0");
  sidebar.classList.add("md:-translate-x-full");
  main.classList.remove("md:ml-[280px]");
  composer.classList.remove("md:left-[280px]");
  desktopHideBtn.classList.add("hidden");
  desktopShowBtn.classList.remove("hidden");
}

/**
 * Initialize the sidebar layout according to the current viewport:
 * - desktop: sidebar visible, overlay hidden, desktop controls enabled
 * - mobile: sidebar closed, overlay used as backdrop, desktop controls hidden
 */
function initSidebarState(ctx) {
  const { sidebar, overlay, main, composer, desktopShowBtn, desktopHideBtn } = ctx;

  if (isDesktop()) {
    // Desktop: no overlay, sidebar docked on the left
    hideOverlay(overlay);
    sidebar.classList.remove("-translate-x-full");
    sidebar.classList.remove("md:-translate-x-full");
    sidebar.classList.add("md:translate-x-0");
    showSidebarDesktop(sidebar, main, composer, desktopShowBtn, desktopHideBtn);
  } else {
    // Mobile: sidebar starts closed, desktop toggle buttons hidden
    closeSidebarMobile(sidebar, overlay);
    desktopShowBtn.classList.add("hidden");
    desktopHideBtn.classList.add("hidden");
  }
}


// ======= Final Function =======
/**
 * Wire sidebar open/close behaviors for mobile and desktop:
 * - off-canvas drawer on mobile with overlay
 * - collapsible fixed sidebar on desktop
 */
export function initSidebar() {
  const sidebar        = document.querySelector("#sidebar");
  const overlay        = document.querySelector("#sidebar-overlay");
  const main           = document.querySelector("#main");
  const composer       = document.querySelector("#composer-bar");
  const openMobileBtn  = document.querySelector("#open-sidebar-btn");
  const closeMobileBtn = document.querySelector("#close-sidebar-btn");
  const desktopHideBtn = document.querySelector("#desktop-hide-btn");
  const desktopShowBtn = document.querySelector("#desktop-show-btn");

  // Bail out if core layout elements are missing
  if (!sidebar || !overlay || !main || !composer) return;

  const ctx = { sidebar, overlay, main, composer, desktopShowBtn, desktopHideBtn };

  // Initial layout + keep it in sync on resize
  initSidebarState(ctx);
  window.addEventListener("resize", () => initSidebarState(ctx));

  // --- Mobile triggers ---
  if (openMobileBtn) {
    openMobileBtn.addEventListener("click", () =>
      openSidebarMobile(sidebar, overlay),
    );
  }
  if (closeMobileBtn) {
    closeMobileBtn.addEventListener("click", () =>
      closeSidebarMobile(sidebar, overlay),
    );
  }
  overlay.addEventListener("click", () =>
    closeSidebarMobile(sidebar, overlay),
  );

  // --- Keyboard: Escape closes sidebar in both modes ---
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!isDesktop()) {
        closeSidebarMobile(sidebar, overlay);
      } else {
        hideSidebarDesktop(sidebar, main, composer, desktopShowBtn, desktopHideBtn);
      }
    }
  });

  // --- Desktop show/hide toggles ---
  if (desktopHideBtn) {
    desktopHideBtn.addEventListener("click", () =>
      hideSidebarDesktop(sidebar, main, composer, desktopShowBtn, desktopHideBtn),
    );
  }
  if (desktopShowBtn) {
    desktopShowBtn.addEventListener("click", () =>
      showSidebarDesktop(sidebar, main, composer, desktopShowBtn, desktopHideBtn),
    );
  }
}

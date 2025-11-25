/**
 * Convert an ISO timestamp into a readable, browser-local datetime string.
 *
 * - Ensures timestamps without a timezone are interpreted as UTC (adds trailing "Z")
 * - Returns the original string unchanged if parsing fails
 * - Formats the timestamp using the user's locale (browser locale)
 */
export function formatLocal(isoString) {
  // Normalize missing timezone → assume UTC if none is present
  let safe = isoString.trim();
  if (safe && !safe.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(safe)) {
    safe = safe + "Z";
  }

  const d = new Date(safe);
  if (isNaN(d.getTime())) {
    return isoString; // Fallback if parsing fails
  }

  // Human-readable local timestamp
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Initialize timestamp formatting inside a given DOM root.
 *
 * - Formats all <time.msg-timestamp> elements in chat messages
 * - Formats all <time.conv-timestamp> elements in the conversations list
 * - Replaces inner text with a human-readable local datetime
 */
export function initTimestamps(root = document) {
  // Chat message timestamps
  root.querySelectorAll("time.msg-timestamp").forEach((el) => {
    const iso = el.getAttribute("datetime") || el.textContent;
    if (!iso) return;

    const formatted = formatLocal(iso);
    el.textContent = formatted;
  });

  // Conversation list timestamps (sidebar)
  root.querySelectorAll("time.conv-timestamp").forEach((el) => {
    const iso = el.getAttribute("datetime") || el.textContent;
    if (!iso) return;

    const formatted = formatLocal(iso);
    el.textContent = formatted;
  });
}

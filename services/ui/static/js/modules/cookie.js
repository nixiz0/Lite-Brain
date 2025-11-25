/**
 * Set a cookie with a given name, value and expiration (in days).
 * Value is URL-encoded. Cookie applies to the entire site.
 */
export function setCookie(name, value, days) {
  const d = new Date();
  // Calculate expiration timestamp (days → ms)
  d.setTime(d.getTime() + days * 24 * 60 * 60 * 1000);
  const expires = "expires=" + d.toUTCString();

  // Write cookie to document with encoded value and root path
  document.cookie = `${name}=${encodeURIComponent(value)};${expires};path=/`;
}

/**
 * Return the value of a cookie by name, or null if not found.
 */
export function getCookie(name) {
  const nameEQ = name + "=";
  const ca = document.cookie.split(";");

  // Iterate through all cookies and match the provided name
  for (let c of ca) {
    c = c.trim();
    if (c.indexOf(nameEQ) === 0) {
      // Return decoded value after name prefix
      return decodeURIComponent(c.substring(nameEQ.length));
    }
  }

  return null;
}

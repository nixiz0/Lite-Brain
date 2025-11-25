const bootstrap = window.__I18N_BOOTSTRAP || { lang: "en", catalog: {} };

const catalog = bootstrap.catalog || {};
const lang = bootstrap.lang || "en";

export { lang };

export function t(key, fallback) {
  if (key in catalog) return catalog[key];
  return fallback || key;
}

// Simple interpolation: replaces {var} with params.var
export function tf(key, params = {}, fallback) {
  let str = t(key, fallback);
  for (const [name, value] of Object.entries(params)) {
    str = str.replaceAll(`{${name}}`, String(value));
  }
  return str;
}

// Optional: Expose globally
window.APP_LANG = lang;
window.__t = t;
window.__tf = tf;

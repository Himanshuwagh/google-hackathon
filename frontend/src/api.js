export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  || (import.meta.env.PROD ? window.location.origin : 'http://127.0.0.1:8000');

export const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');

export async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const message = payload?.message || payload?.detail || `Request failed (${response.status})`;
    throw new Error(message);
  }

  return payload;
}

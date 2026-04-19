// Per-browser session identifier — sent as `X-Session-Id` on every agent
// request so Langfuse traces from the same tab group together and the
// backend rate limiter buckets requests by session rather than IP.
//
// Persists in localStorage so a page refresh keeps the same trace timeline.
// Cleared by the user clearing site data; we never expose a "reset" action.

const STORAGE_KEY = "fpl.sessionId";

export function getSessionId(): string {
  if (typeof window === "undefined") return "ssr";
  let id = window.localStorage.getItem(STORAGE_KEY);
  if (!id) {
    id = window.crypto.randomUUID();
    window.localStorage.setItem(STORAGE_KEY, id);
  }
  return id;
}

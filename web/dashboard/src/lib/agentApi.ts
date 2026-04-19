import type {
  AgentEvent,
  AgentResponse,
  ChatRequest,
  UserSquad,
} from "./types";
import { getSessionId } from "./sessionId";

// All agent calls go through `/api/agent/*`. In dev, Vite proxies this to
// the CloudFront origin (see vite.config.ts). In prod, CloudFront fronts
// both the static dashboard and the agent Lambda — same origin, no CORS
// preflight, identical path.
const AGENT_BASE = "/api/agent";

export class AgentApiError extends Error {
  readonly status: number;
  readonly retryAfter?: number;

  constructor(message: string, status: number, retryAfter?: number) {
    super(message);
    this.name = "AgentApiError";
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

function authHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Session-Id": getSessionId(),
  };
}

/** Fetch and enrich a user's FPL squad for one gameweek. */
export async function fetchTeam(
  teamId: number,
  gameweek: number,
  signal?: AbortSignal,
): Promise<UserSquad> {
  const url = `${AGENT_BASE}/team?team_id=${teamId}&gameweek=${gameweek}`;
  const res = await fetch(url, { headers: authHeaders(), signal });
  if (!res.ok) {
    const detail = await safeReadDetail(res);
    throw new AgentApiError(detail, res.status);
  }
  return parseJsonOrThrow<UserSquad>(res);
}

/** POST /chat/sync — blocking JSON. Used for tests and as a fallback. */
export async function chatSync(
  req: ChatRequest,
  signal?: AbortSignal,
): Promise<AgentResponse> {
  const res = await fetch(`${AGENT_BASE}/chat/sync`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(req),
    signal,
  });
  if (!res.ok) {
    const detail = await safeReadDetail(res);
    const retry = parseRetryAfter(res.headers.get("Retry-After"));
    throw new AgentApiError(detail, res.status, retry);
  }
  return parseJsonOrThrow<AgentResponse>(res);
}

/**
 * POST /chat — async generator over SSE. Yields each `step`/`result`/`error`
 * event in order. We can't use the browser's `EventSource` because it only
 * does GET; we drive the stream by hand with `fetch` + `ReadableStream`.
 *
 * The caller is responsible for cancellation via `signal.abort()` — when
 * the AbortSignal fires the underlying fetch closes and the generator
 * returns cleanly.
 */
export async function* streamChat(
  req: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent, void, void> {
  const res = await fetch(`${AGENT_BASE}/chat`, {
    method: "POST",
    headers: { ...authHeaders(), Accept: "text/event-stream" },
    body: JSON.stringify(req),
    signal,
  });
  if (!res.ok) {
    const detail = await safeReadDetail(res);
    const retry = parseRetryAfter(res.headers.get("Retry-After"));
    throw new AgentApiError(detail, res.status, retry);
  }
  if (!res.body) {
    throw new AgentApiError("agent returned an empty stream", res.status);
  }
  yield* parseSseStream(res.body);
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

async function* parseSseStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<AgentEvent, void, void> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line. Process every complete
      // frame in the buffer; leave the remainder for the next chunk.
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const event = parseFrame(frame);
        if (event) yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/** Parse one SSE frame ("event: x\ndata: {...}") into an AgentEvent. */
function parseFrame(frame: string): AgentEvent | null {
  let eventName = "";
  const dataLines: string[] = [];

  for (const raw of frame.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith(":")) continue; // blank or comment
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!eventName) return null;

  const data = dataLines.join("\n");
  try {
    const parsed = data ? JSON.parse(data) : {};
    if (eventName === "step") {
      return { type: "step", node: String(parsed.node ?? "") };
    }
    if (eventName === "result") {
      return { type: "result", payload: parsed as AgentResponse };
    }
    if (eventName === "error") {
      return { type: "error", message: String(parsed.message ?? "unknown error") };
    }
    return null;
  } catch {
    // sse-starlette pings (no data, or non-JSON) — skip silently.
    return null;
  }
}

/**
 * Parse JSON with a friendly error when the body is HTML. CloudFront serves
 * the SPA fallback (`/index.html` with HTTP 200) for upstream 4xx/5xx, so a
 * mis-configured agent endpoint surfaces here as `<!doctype …>` instead of
 * the JSON we asked for. The native parser error in that case is a cryptic
 * `Unexpected token '<'`; this hint points at the actual problem.
 */
async function parseJsonOrThrow<T>(res: Response): Promise<T> {
  const text = await res.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    if (text.trimStart().startsWith("<")) {
      throw new AgentApiError(
        "Agent endpoint returned HTML instead of JSON — the Lambda Function URL is unreachable. Run terraform apply to install the Function URL invoke permission.",
        502,
      );
    }
    throw new AgentApiError(`Invalid JSON from agent: ${text.slice(0, 80)}`, 502);
  }
}

async function safeReadDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body === "string") return body;
    if (body?.detail) {
      return typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail);
    }
    return JSON.stringify(body);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

function parseRetryAfter(value: string | null): number | undefined {
  if (!value) return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

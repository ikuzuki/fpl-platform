import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AgentApiError, fetchTeam, streamChat } from "./agentApi";
import type { AgentEvent, UserSquad } from "./types";

const mockSquad: UserSquad = {
  team_id: 1,
  gameweek: 33,
  picks: [],
  bank: 0.5,
  total_value: 100.4,
  active_chip: null,
  overall_rank: 12345,
  total_points: 1500,
};

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

function sseStreamFromFrames(frames: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });
}

describe("fetchTeam", () => {
  it("returns parsed UserSquad on 200", async () => {
    const fetchSpy = vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockSquad), { status: 200 }),
    );

    const result = await fetchTeam(1, 33);
    expect(result).toEqual(mockSquad);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/agent/team?team_id=1&gameweek=33");
    const headers = init.headers as Record<string, string>;
    expect(headers["X-Session-Id"]).toBeTruthy();
  });

  it("throws AgentApiError with status code on 4xx", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "team not found" }), { status: 404 }),
    );
    await expect(fetchTeam(999, 33)).rejects.toMatchObject({
      name: "AgentApiError",
      status: 404,
    });
  });
});

describe("streamChat", () => {
  it("yields step + result events parsed from the SSE stream", async () => {
    const frames = [
      "event: step\ndata: {\"node\":\"planner\"}\n\n",
      "event: step\ndata: {\"node\":\"recommender\"}\n\n",
      `event: result\ndata: ${JSON.stringify({
        report: {
          question: "q",
          analysis: "a",
          players: [],
          comparison: null,
          recommendation: "r",
          caveats: [],
          data_sources: [],
        },
        iterations_used: 1,
        tool_calls_made: [],
      })}\n\n`,
    ];
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(sseStreamFromFrames(frames), {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );

    const events: AgentEvent[] = [];
    for await (const e of streamChat({ question: "q" })) {
      events.push(e);
    }
    expect(events).toHaveLength(3);
    expect(events[0]).toEqual({ type: "step", node: "planner" });
    expect(events[1]).toEqual({ type: "step", node: "recommender" });
    expect(events[2].type).toBe("result");
  });

  it("handles frames split across stream chunks", async () => {
    // Real SSE chunks don't always align to frame boundaries — half of one
    // frame can land in the next read. The parser must buffer.
    const frames = [
      "event: step\ndata: {\"node\":\"plan",
      "ner\"}\n\nevent: step\ndata: {\"node\":\"recommender\"}\n\n",
    ];
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(sseStreamFromFrames(frames), { status: 200 }),
    );

    const events: AgentEvent[] = [];
    for await (const e of streamChat({ question: "q" })) {
      events.push(e);
    }
    expect(events).toEqual([
      { type: "step", node: "planner" },
      { type: "step", node: "recommender" },
    ]);
  });

  it("throws AgentApiError on 429 with Retry-After", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "rate_limit_exceeded" }), {
        status: 429,
        headers: { "Retry-After": "30" },
      }),
    );

    await expect(async () => {
      const stream = streamChat({ question: "q" });
      // The error is thrown by the initial fetch + status check inside the
      // generator before any event yields, so simply iterating triggers it.
      for await (const event of stream) {
        // never reached — drop reference so the iterator can drain
        void event;
      }
    }).rejects.toMatchObject({
      name: "AgentApiError",
      status: 429,
      retryAfter: 30,
    });
  });

  it("AgentApiError type carries status", () => {
    const err = new AgentApiError("x", 503);
    expect(err.status).toBe(503);
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ChatPage } from "./ChatPage";
import * as agentApi from "@/lib/agentApi";
import * as apiModule from "@/lib/api";
import type { AgentEvent, AgentResponse } from "@/lib/types";

const mockResponse: AgentResponse = {
  report: {
    question: "Is Salah worth £13.0m right now?",
    analysis: "Yes — Salah is in elite form.",
    players: [
      {
        player_name: "Salah",
        position: "MID",
        price: 13.0,
        form: 7.5,
        fixture_outlook: "green",
        verdict: "Continued elite returns expected.",
        confidence: 0.85,
      },
    ],
    comparison: null,
    recommendation: "Hold or buy.",
    caveats: ["Fixture data limited to next 3 GWs."],
    data_sources: ["query_player", "get_fixture_outlook"],
  },
  iterations_used: 2,
  tool_calls_made: ["query_player", "get_fixture_outlook"],
};

async function* mockStream(events: AgentEvent[]): AsyncGenerator<AgentEvent, void, void> {
  for (const e of events) yield e;
}

beforeEach(() => {
  window.localStorage.clear();
  // ChatPage calls api.briefing() to discover current gameweek; stub it.
  vi.spyOn(apiModule.api, "briefing").mockResolvedValue({
    gameweek: 33,
    season: "2025-26",
    top_picks: [],
    sell_alerts: [],
    injury_alerts: [],
    best_fixtures: [],
    worst_fixtures: [],
    rising_players: [],
    falling_players: [],
    trending_themes: [],
    summary_stats: {
      total_players: 0,
      buy_count: 0,
      sell_count: 0,
      injury_count: 0,
      improving_count: 0,
      declining_count: 0,
    },
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <ChatPage />
    </MemoryRouter>,
  );
}

describe("ChatPage", () => {
  it("renders hero, team ID input, and suggested general questions in empty state", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: /scout/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/load your squad/i)).toBeInTheDocument();
    // Suggested questions
    expect(screen.getByText(/is salah worth/i)).toBeInTheDocument();
  });

  it("submits a question, streams steps, and renders the final report", async () => {
    vi.spyOn(agentApi, "streamChat").mockReturnValue(
      mockStream([
        { type: "step", node: "planner" },
        { type: "step", node: "tool_executor" },
        { type: "step", node: "recommender" },
        { type: "result", payload: mockResponse },
      ]),
    );

    renderPage();
    const input = await screen.findByLabelText(/ask the scout agent/i);
    fireEvent.change(input, {
      target: { value: "Is Salah worth £13.0m right now?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    // User message renders immediately
    expect(
      await screen.findByText("Is Salah worth £13.0m right now?"),
    ).toBeInTheDocument();
    // Final report renders after stream completes
    await waitFor(() =>
      expect(
        screen.getByText(/salah is in elite form/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/hold or buy/i)).toBeInTheDocument();
    // Caveat surfaced
    expect(
      screen.getByText(/fixture data limited to next 3 GWs/i),
    ).toBeInTheDocument();
  });

  it("clicking a suggested question sends it without typing", async () => {
    const streamSpy = vi.spyOn(agentApi, "streamChat").mockReturnValue(
      mockStream([{ type: "result", payload: mockResponse }]),
    );

    renderPage();
    const suggested = await screen.findByRole("button", {
      name: /is salah worth £13/i,
    });
    fireEvent.click(suggested);

    await waitFor(() => expect(streamSpy).toHaveBeenCalled());
    const [req] = streamSpy.mock.calls[0];
    expect(req.question).toMatch(/is salah worth/i);
    expect(req.squad).toBeUndefined();
  });

  it("retry button re-sends the previous user message after an error", async () => {
    const streamSpy = vi
      .spyOn(agentApi, "streamChat")
      .mockReturnValueOnce(mockStream([{ type: "error", message: "boom" }]))
      .mockReturnValueOnce(mockStream([{ type: "result", payload: mockResponse }]));

    renderPage();
    const input = await screen.findByLabelText(/ask the scout agent/i);
    fireEvent.change(input, { target: { value: "Captain pick?" } });
    fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    const retryButton = await screen.findByRole("button", { name: /retry/i });
    fireEvent.click(retryButton);

    await waitFor(() =>
      expect(
        screen.getByText(/salah is in elite form/i),
      ).toBeInTheDocument(),
    );
    expect(streamSpy).toHaveBeenCalledTimes(2);
    expect(streamSpy.mock.calls[1][0].question).toBe("Captain pick?");
  });

  it("new chat button clears messages and returns to the empty state", async () => {
    vi.spyOn(agentApi, "streamChat").mockReturnValue(
      mockStream([{ type: "result", payload: mockResponse }]),
    );

    renderPage();
    const input = await screen.findByLabelText(/ask the scout agent/i);
    fireEvent.change(input, { target: { value: "anything" } });
    fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() =>
      expect(screen.getByText(/salah is in elite form/i)).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: /new chat/i }));

    expect(screen.queryByText(/salah is in elite form/i)).not.toBeInTheDocument();
    // Suggested questions reappear in the empty state
    expect(screen.getByText(/is salah worth/i)).toBeInTheDocument();
  });
});

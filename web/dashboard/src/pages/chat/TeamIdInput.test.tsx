import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TeamIdInput } from "./TeamIdInput";
import type { UserSquad } from "@/lib/types";
import * as agentApi from "@/lib/agentApi";

const mockSquad: UserSquad = {
  team_id: 5767400,
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

describe("TeamIdInput", () => {
  it("calls fetchTeam, persists ID, and notifies parent on success", async () => {
    const fetchSpy = vi.spyOn(agentApi, "fetchTeam").mockResolvedValue(mockSquad);
    const onLoaded = vi.fn();

    render(
      <TeamIdInput
        gameweek={33}
        squad={null}
        onLoaded={onLoaded}
        onCleared={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/load your squad/i), {
      target: { value: "5767400" },
    });
    fireEvent.click(screen.getByRole("button", { name: /load squad/i }));

    await waitFor(() => expect(onLoaded).toHaveBeenCalledWith(mockSquad));
    expect(fetchSpy).toHaveBeenCalledWith(5767400, 33);
    expect(window.localStorage.getItem("fpl.teamId")).toBe("5767400");
  });

  it("renders inline error on 404 from backend", async () => {
    vi.spyOn(agentApi, "fetchTeam").mockRejectedValue(
      new agentApi.AgentApiError("not found", 404),
    );

    render(
      <TeamIdInput
        gameweek={33}
        squad={null}
        onLoaded={vi.fn()}
        onCleared={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/load your squad/i), {
      target: { value: "999" },
    });
    fireEvent.click(screen.getByRole("button", { name: /load squad/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/not found/i);
  });

  it("rejects non-integer input without calling fetchTeam", async () => {
    const fetchSpy = vi.spyOn(agentApi, "fetchTeam");

    render(
      <TeamIdInput
        gameweek={33}
        squad={null}
        onLoaded={vi.fn()}
        onCleared={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/load your squad/i), {
      target: { value: "abc" },
    });
    fireEvent.click(screen.getByRole("button", { name: /load squad/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/valid fpl team id/i);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

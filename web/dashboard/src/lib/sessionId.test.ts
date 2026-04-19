import { afterEach, describe, expect, it } from "vitest";
import { getSessionId } from "./sessionId";

afterEach(() => {
  window.localStorage.clear();
});

describe("getSessionId", () => {
  it("generates and persists a UUID on first call", () => {
    const id = getSessionId();
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
    expect(window.localStorage.getItem("fpl.sessionId")).toBe(id);
  });

  it("reuses the persisted id on subsequent calls", () => {
    const first = getSessionId();
    const second = getSessionId();
    expect(second).toBe(first);
  });
});

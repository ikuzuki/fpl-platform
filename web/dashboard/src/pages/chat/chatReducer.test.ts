import { describe, expect, it } from "vitest";
import {
  chatReducer,
  initialChatState,
  type AssistantMessage,
} from "./chatReducer";
import type { AgentResponse } from "@/lib/types";

const mockResponse: AgentResponse = {
  report: {
    question: "test",
    analysis: "ok",
    players: [],
    comparison: null,
    recommendation: "buy",
    caveats: [],
    data_sources: ["query_player"],
  },
  iterations_used: 1,
  tool_calls_made: ["query_player"],
};

describe("chatReducer", () => {
  it("USER_SENT appends user + streaming assistant and sets pendingId", () => {
    const next = chatReducer(initialChatState, {
      type: "USER_SENT",
      userId: "u1",
      assistantId: "a1",
      text: "Is Salah worth it?",
    });

    expect(next.messages).toHaveLength(2);
    expect(next.messages[0]).toMatchObject({ role: "user", text: "Is Salah worth it?" });
    expect(next.messages[1]).toMatchObject({
      role: "assistant",
      status: "streaming",
      steps: [],
      response: null,
    });
    expect(next.pendingId).toBe("a1");
  });

  it("STEP appends node names to the in-flight assistant message only", () => {
    let state = chatReducer(initialChatState, {
      type: "USER_SENT",
      userId: "u1",
      assistantId: "a1",
      text: "q",
    });
    state = chatReducer(state, { type: "STEP", node: "planner" });
    state = chatReducer(state, { type: "STEP", node: "tool_executor" });

    const assistant = state.messages[1] as AssistantMessage;
    expect(assistant.steps).toEqual(["planner", "tool_executor"]);
  });

  it("RESULT marks complete, attaches response, clears pendingId", () => {
    let state = chatReducer(initialChatState, {
      type: "USER_SENT",
      userId: "u1",
      assistantId: "a1",
      text: "q",
    });
    state = chatReducer(state, { type: "RESULT", payload: mockResponse });

    const assistant = state.messages[1] as AssistantMessage;
    expect(assistant.status).toBe("complete");
    expect(assistant.response).toEqual(mockResponse);
    expect(state.pendingId).toBeNull();
  });

  it("ERROR marks error + stores message, clears pendingId", () => {
    let state = chatReducer(initialChatState, {
      type: "USER_SENT",
      userId: "u1",
      assistantId: "a1",
      text: "q",
    });
    state = chatReducer(state, { type: "ERROR", message: "boom" });

    const assistant = state.messages[1] as AssistantMessage;
    expect(assistant.status).toBe("error");
    expect(assistant.error).toBe("boom");
    expect(state.pendingId).toBeNull();
  });

  it("RESET wipes everything", () => {
    let state = chatReducer(initialChatState, {
      type: "USER_SENT",
      userId: "u1",
      assistantId: "a1",
      text: "q",
    });
    state = chatReducer(state, { type: "RESET" });
    expect(state).toEqual(initialChatState);
  });

  it("STEP after RESULT does not mutate the now-completed assistant message", () => {
    // Defensive: a stray late `step` event from a slow stream must not append
    // to a message that has already settled.
    let state = chatReducer(initialChatState, {
      type: "USER_SENT",
      userId: "u1",
      assistantId: "a1",
      text: "q",
    });
    state = chatReducer(state, { type: "RESULT", payload: mockResponse });
    const before = state.messages[1] as AssistantMessage;
    state = chatReducer(state, { type: "STEP", node: "late" });
    const after = state.messages[1] as AssistantMessage;
    expect(after.steps).toEqual(before.steps);
  });
});

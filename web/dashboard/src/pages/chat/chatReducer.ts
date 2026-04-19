import type { AgentResponse } from "@/lib/types";

// Chat history is a flat list of messages. Assistant messages carry the
// full streaming lifecycle: which nodes have fired, the final report when
// it lands, an error if the run failed.
export type AssistantStatus = "streaming" | "complete" | "error";

export interface UserMessage {
  id: string;
  role: "user";
  text: string;
}

export interface AssistantMessage {
  id: string;
  role: "assistant";
  status: AssistantStatus;
  steps: string[]; // node names in order received
  response: AgentResponse | null;
  error: string | null;
}

export type ChatMessage = UserMessage | AssistantMessage;

export interface ChatState {
  messages: ChatMessage[];
  // Convenience pointer to the in-flight assistant message id. Lets the
  // page disable input + show a stop button without scanning the list.
  pendingId: string | null;
}

export const initialChatState: ChatState = {
  messages: [],
  pendingId: null,
};

export type ChatAction =
  | { type: "USER_SENT"; userId: string; assistantId: string; text: string }
  | { type: "STEP"; node: string }
  | { type: "RESULT"; payload: AgentResponse }
  | { type: "ERROR"; message: string }
  | { type: "RESET" };

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "USER_SENT": {
      const user: UserMessage = {
        id: action.userId,
        role: "user",
        text: action.text,
      };
      const assistant: AssistantMessage = {
        id: action.assistantId,
        role: "assistant",
        status: "streaming",
        steps: [],
        response: null,
        error: null,
      };
      return {
        messages: [...state.messages, user, assistant],
        pendingId: action.assistantId,
      };
    }
    case "STEP":
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === state.pendingId && m.role === "assistant"
            ? { ...m, steps: [...m.steps, action.node] }
            : m,
        ),
      };
    case "RESULT":
      return {
        pendingId: null,
        messages: state.messages.map((m) =>
          m.id === state.pendingId && m.role === "assistant"
            ? { ...m, status: "complete", response: action.payload }
            : m,
        ),
      };
    case "ERROR":
      return {
        pendingId: null,
        messages: state.messages.map((m) =>
          m.id === state.pendingId && m.role === "assistant"
            ? { ...m, status: "error", error: action.message }
            : m,
        ),
      };
    case "RESET":
      return initialChatState;
  }
}

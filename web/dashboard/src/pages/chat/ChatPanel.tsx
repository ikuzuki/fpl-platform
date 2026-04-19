import { useEffect, useReducer, useRef, type FormEvent } from "react";
import { Send, Square, AlertTriangle, Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { AgentApiError, streamChat } from "@/lib/agentApi";
import type { UserSquad } from "@/lib/types";
import { chatReducer, initialChatState, type ChatMessage } from "./chatReducer";
import { ScoutReportCard } from "./ScoutReportCard";
import { StepPills } from "./StepPills";

const GENERAL_QUESTIONS = [
  "Is Salah worth £13.0m right now?",
  "Compare Palmer and Saka over the next 5 GWs",
  "Best budget midfielder under £6.0m?",
];

const TEAM_QUESTIONS = [
  "Who should I captain this week?",
  "What transfer should I make next?",
  "Which of my players is the biggest sell risk?",
];

interface ChatPanelProps {
  squad: UserSquad | null;
  /** Drawer mode tightens spacing and hides the trailing data-source line. */
  compact?: boolean;
}

export function ChatPanel({ squad, compact = false }: ChatPanelProps) {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const streaming = state.pendingId !== null;

  useEffect(() => {
    // Cancel any in-flight stream when the panel unmounts. Without this a
    // user navigating away mid-stream would leave a hanging fetch + a
    // stale Langfuse trace open until the server timed out.
    return () => abortRef.current?.abort();
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && typeof el.scrollTo === "function") {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [state.messages]);

  async function send(text: string) {
    if (!text.trim() || streaming) return;
    const userId = crypto.randomUUID();
    const assistantId = crypto.randomUUID();
    dispatch({ type: "USER_SENT", userId, assistantId, text });

    const controller = new AbortController();
    abortRef.current = controller;

    let settled = false;
    try {
      const stream = streamChat(
        { question: text, squad: squad ?? undefined },
        controller.signal,
      );
      for await (const event of stream) {
        if (event.type === "step") {
          dispatch({ type: "STEP", node: event.node });
        } else if (event.type === "result") {
          settled = true;
          dispatch({ type: "RESULT", payload: event.payload });
        } else if (event.type === "error") {
          settled = true;
          dispatch({ type: "ERROR", message: event.message });
        }
      }
      // If the stream ended without a terminal event we still need to
      // close out the assistant message — treat as error so the UI
      // doesn't sit forever in "streaming" state.
      if (!settled) {
        dispatch({ type: "ERROR", message: "Stream ended before a final report." });
      }
    } catch (e) {
      if (controller.signal.aborted) {
        dispatch({ type: "ERROR", message: "Cancelled." });
        return;
      }
      const message = formatError(e);
      dispatch({ type: "ERROR", message });
    } finally {
      abortRef.current = null;
    }
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const value = inputRef.current?.value ?? "";
    if (!value.trim()) return;
    void send(value);
    if (inputRef.current) inputRef.current.value = "";
  }

  function handleStop() {
    abortRef.current?.abort();
  }

  function handleSuggested(text: string) {
    if (inputRef.current) inputRef.current.value = text;
    void send(text);
  }

  return (
    <div className={cn("flex flex-col gap-3", compact ? "h-full" : "min-h-[560px]")}>
      <div
        ref={scrollRef}
        className={cn(
          "flex-1 overflow-y-auto space-y-3 pr-1",
          compact ? "min-h-[280px]" : "min-h-[400px]",
        )}
      >
        {state.messages.length === 0 && (
          <EmptyState
            squadLoaded={squad !== null}
            onPick={handleSuggested}
            compact={compact}
          />
        )}
        {state.messages.map((m) => (
          <MessageView key={m.id} message={m} compact={compact} />
        ))}
      </div>

      <form
        onSubmit={handleSubmit}
        className="flex items-end gap-2 border-t border-[var(--border)] pt-3"
      >
        <input
          ref={inputRef}
          type="text"
          placeholder={
            squad
              ? "Ask about your squad — captain, transfers, sell risk…"
              : "Ask anything about FPL — players, fixtures, comparisons…"
          }
          aria-label="Ask the scout agent"
          maxLength={500}
          disabled={streaming}
          className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] disabled:opacity-50"
        />
        {streaming ? (
          <button
            type="button"
            onClick={handleStop}
            aria-label="Stop"
            className="rounded-md bg-[var(--danger)]/90 px-3 py-2 text-sm font-medium text-white hover:opacity-90 inline-flex items-center gap-1.5"
          >
            <Square className="h-3.5 w-3.5" />
            Stop
          </button>
        ) : (
          <button
            type="submit"
            aria-label="Send"
            className="rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-medium text-[var(--accent-foreground)] hover:opacity-90 inline-flex items-center gap-1.5"
          >
            <Send className="h-3.5 w-3.5" />
            Ask
          </button>
        )}
      </form>
    </div>
  );
}

function EmptyState({
  squadLoaded,
  onPick,
  compact,
}: {
  squadLoaded: boolean;
  onPick: (text: string) => void;
  compact: boolean;
}) {
  return (
    <div className={cn("text-center space-y-4", compact ? "py-4" : "py-8")}>
      <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-[var(--ai-bg)] border border-[var(--ai-border)]">
        <Sparkles className="h-5 w-5 text-[var(--accent)]" />
      </div>
      <div>
        <p className="font-semibold text-base">
          {squadLoaded ? "Ready to talk about your squad" : "Ask anything about FPL"}
        </p>
        <p className="text-xs text-[var(--muted-foreground)] mt-1">
          {squadLoaded
            ? "Now I can give advice tailored to your players. Try one of these:"
            : "Or load your team ID above for personalised advice. Try one of these:"}
        </p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center">
        {(squadLoaded ? TEAM_QUESTIONS : GENERAL_QUESTIONS).map((q) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            className="rounded-full border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageView({ message, compact }: { message: ChatMessage; compact: boolean }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg bg-[var(--accent)] text-[var(--accent-foreground)] px-3 py-2 text-sm">
          {message.text}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <StepPills steps={message.steps} active={message.status === "streaming"} />
      {message.status === "error" && message.error && (
        <Card className="border-[var(--danger)]/40">
          <CardContent className="py-3 flex items-start gap-2 text-sm">
            <AlertTriangle className="h-4 w-4 text-[var(--danger)] mt-0.5 shrink-0" />
            <span>{message.error}</span>
          </CardContent>
        </Card>
      )}
      {message.response && (
        <ScoutReportCard response={message.response} compact={compact} />
      )}
    </div>
  );
}

function formatError(e: unknown): string {
  if (e instanceof AgentApiError) {
    if (e.status === 429) {
      return e.retryAfter
        ? `Rate limited — try again in ${e.retryAfter}s.`
        : "The agent is at its monthly budget cap. Try again later.";
    }
    if (e.status === 503) return "Agent is starting up — try again in a moment.";
    return `Agent error (${e.status}): ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return "Something went wrong.";
}

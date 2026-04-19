import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

// Mirrors graph node order from services/agent/src/fpl_agent/graph/builder.py.
// Tool executor is collapsed into "tools" for friendlier UI labelling.
const NODE_LABELS: Record<string, string> = {
  planner: "Planning",
  tool_executor: "Gathering data",
  reflector: "Reviewing",
  recommender: "Writing report",
};

const NODE_ORDER = ["planner", "tool_executor", "reflector", "recommender"];

interface StepPillsProps {
  steps: string[];
  /** True while we're still expecting more events. */
  active: boolean;
}

export function StepPills({ steps, active }: StepPillsProps) {
  if (steps.length === 0 && !active) return null;
  const seen = new Set(steps);
  const lastStep = steps[steps.length - 1];

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {NODE_ORDER.map((node) => {
        const done = seen.has(node);
        const inFlight = active && node === lastStep;
        const label = NODE_LABELS[node] ?? node;
        return (
          <span
            key={node}
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] transition-colors",
              done
                ? "border-[var(--accent)] bg-[var(--ai-bg)] text-[var(--accent)]"
                : "border-[var(--border)] text-[var(--muted-foreground)]",
            )}
          >
            {inFlight ? (
              <Loader2 className="h-2.5 w-2.5 animate-spin" />
            ) : done ? (
              <Check className="h-2.5 w-2.5" />
            ) : (
              <span className="h-2.5 w-2.5 rounded-full border border-current opacity-40" />
            )}
            {label}
          </span>
        );
      })}
    </div>
  );
}

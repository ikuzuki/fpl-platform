import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "./card";

export function ErrorCard({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card className="border-[var(--danger)]/30">
      <CardContent className="pt-4 flex flex-col items-center text-center gap-3 py-8">
        <AlertTriangle className="h-8 w-8 text-[var(--danger)]" />
        <div>
          <p className="font-medium">Failed to load data</p>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">{message}</p>
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="rounded-md bg-[var(--accent)] px-4 py-1.5 text-sm font-medium text-[var(--accent-foreground)] hover:opacity-90 transition-opacity"
          >
            Retry
          </button>
        )}
      </CardContent>
    </Card>
  );
}

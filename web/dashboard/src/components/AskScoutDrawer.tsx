import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Sparkles, X, ArrowUpRight } from "lucide-react";
import { ChatPanel } from "@/pages/chat/ChatPanel";
import { cn } from "@/lib/utils";

// Floating "Ask Scout" surface available on every page. Hosts the same
// ChatPanel as /chat — drawer mode passes `compact` so the report card
// tightens spacing. Squad rendering is intentionally NOT included here:
// the XI grid is too cramped at 400px and the drawer is meant for quick
// questions, not the full squad consultation flow.

export function AskScoutDrawer() {
  const [open, setOpen] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const fabRef = useRef<HTMLButtonElement>(null);
  const location = useLocation();

  // Hide on the dedicated page itself — the FAB would be redundant and
  // would also obscure the page's own send button on mobile.
  const onChatPage = location.pathname === "/chat";

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    closeButtonRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  // Restore focus to the FAB when closing so keyboard users land back
  // somewhere predictable.
  useEffect(() => {
    if (!open) fabRef.current?.focus({ preventScroll: true });
  }, [open]);

  if (onChatPage) return null;

  return (
    <>
      <button
        ref={fabRef}
        onClick={() => setOpen(true)}
        aria-label="Open Scout chat"
        aria-expanded={open}
        className={cn(
          "fixed bottom-5 right-5 z-40 inline-flex items-center gap-2",
          "rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-medium text-[var(--accent-foreground)]",
          "shadow-lg hover:shadow-xl hover:scale-105 transition-transform",
          "focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:ring-offset-2",
          open && "opacity-0 pointer-events-none",
        )}
      >
        <Sparkles className="h-4 w-4" />
        <span className="hidden sm:inline">Ask Scout</span>
      </button>

      {/* Always rendered so we can transition the transform/opacity instead of
          mount/unmount. Closed state is inert: pointer-events off + aria-hidden,
          so keyboard focus and clicks pass through to the page underneath. */}
      <div
        className={cn(
          "fixed inset-0 z-50",
          open ? "pointer-events-auto" : "pointer-events-none",
        )}
        role="dialog"
        aria-modal="true"
        aria-label="Scout quick chat"
        aria-hidden={!open}
      >
        {/* Backdrop — barely-visible click-catcher. Keeps "click outside to
            close" working without the heavy blur the user found jarring. */}
        <button
          type="button"
          aria-label="Close drawer"
          tabIndex={open ? 0 : -1}
          onClick={() => setOpen(false)}
          className={cn(
            "absolute inset-0 bg-black/40 transition-opacity duration-200",
            open ? "opacity-100" : "opacity-0",
          )}
        />
        <aside
          className={cn(
            "absolute right-0 top-0 h-full w-full sm:w-[420px]",
            "bg-[var(--card)] border-l border-[var(--border)] shadow-2xl",
            "flex flex-col",
            "transition-transform duration-300 ease-out will-change-transform",
            open ? "translate-x-0" : "translate-x-full",
          )}
        >
          <header className="flex items-center justify-between gap-2 px-4 py-3 border-b border-[var(--border)]">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-[var(--accent)]" />
              <span className="font-semibold text-sm">Ask Scout</span>
            </div>
            <div className="flex items-center gap-1">
              <Link
                to="/chat"
                onClick={() => setOpen(false)}
                tabIndex={open ? 0 : -1}
                className="text-xs text-[var(--muted-foreground)] hover:text-[var(--accent)] inline-flex items-center gap-1"
              >
                Open full view
                <ArrowUpRight className="h-3 w-3" />
              </Link>
              <button
                ref={closeButtonRef}
                onClick={() => setOpen(false)}
                aria-label="Close drawer"
                tabIndex={open ? 0 : -1}
                className="rounded-md p-1 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </header>
          <div className="flex-1 overflow-hidden p-3">
            <ChatPanel squad={null} compact />
          </div>
        </aside>
      </div>
    </>
  );
}

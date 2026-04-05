import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Moon, Sun, Menu, X } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const links = [
  { to: "/", label: "Briefing" },
  { to: "/players", label: "Players" },
  { to: "/fixtures", label: "Fixtures" },
  { to: "/transfers", label: "Transfers" },
  { to: "/teams", label: "Teams" },
  { to: "/trends", label: "Trends" },
  { to: "/captain", label: "Captain" },
  { to: "/differentials", label: "Differentials" },
  { to: "/planner", label: "Planner" },
];

export function Layout() {
  const [dark, setDark] = useState(() => {
    if (typeof window === "undefined") return false;
    const stored = localStorage.getItem("theme");
    if (stored) return stored === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  const [menuOpen, setMenuOpen] = useState(false);
  const [footerInfo, setFooterInfo] = useState<{ gameweek: number; season: string } | null>(null);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    api.briefing().then((b) => setFooterInfo({ gameweek: b.gameweek, season: b.season })).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[var(--background)]">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>

      <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--card)]/80 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-8">
            <span className="text-lg font-bold tracking-tight">
              <span className="text-[var(--accent)]">FPL</span> Analytics
            </span>
            <nav className="hidden md:flex gap-1" aria-label="Main navigation">
              {links.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  className={({ isActive }) =>
                    cn(
                      "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                        : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]",
                    )
                  }
                >
                  {link.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setDark(!dark)}
              className="rounded-md p-2 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
              aria-label="Toggle dark mode"
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="md:hidden rounded-md p-2 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              aria-expanded={menuOpen}
            >
              {menuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>
        </div>
        {menuOpen && (
          <nav className="md:hidden border-t border-[var(--border)] bg-[var(--card)] px-6 py-3 space-y-1" aria-label="Mobile navigation">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "block rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]",
                  )
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>
      <main id="main-content" className="mx-auto max-w-7xl px-6 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-[var(--border)] py-4 text-center text-xs text-[var(--muted-foreground)]">
        {footerInfo
          ? `Last updated: GW${footerInfo.gameweek}, ${footerInfo.season}`
          : "Data refreshed weekly via automated pipeline"}{" "}
        &middot; Powered by Claude AI enrichment
      </footer>
    </div>
  );
}

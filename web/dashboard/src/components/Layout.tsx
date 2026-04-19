import { useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Moon,
  Sun,
  Menu,
  X,
  Crown,
  Target,
  ArrowRightLeft,
  Info,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { PulseLogo, PulseWordmark, NavIcons } from "@/components/icons/FplIcons";
import { AskScoutDrawer } from "@/components/AskScoutDrawer";

const links: { to: string; label: string; icon: ReactNode }[] = [
  { to: "/", label: "Briefing", icon: <NavIcons.Briefing size={16} /> },
  { to: "/captain", label: "Captain", icon: <Crown className="h-4 w-4" /> },
  { to: "/transfers", label: "Transfers", icon: <NavIcons.Transfers size={16} /> },
  { to: "/planner", label: "Planner", icon: <ArrowRightLeft className="h-4 w-4" /> },
  { to: "/players", label: "Players", icon: <NavIcons.Players size={16} /> },
  { to: "/differentials", label: "Differentials", icon: <Target className="h-4 w-4" /> },
  { to: "/fixtures", label: "Fixtures", icon: <NavIcons.Fixtures size={16} /> },
  { to: "/teams", label: "Teams", icon: <NavIcons.Teams size={16} /> },
  { to: "/trends", label: "Trends", icon: <NavIcons.Trends size={16} /> },
  { to: "/about", label: "About", icon: <Info className="h-4 w-4" /> },
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
            <NavLink to="/" className="flex items-center gap-2.5">
              <PulseLogo size={28} />
              <PulseWordmark size={100} className="hidden sm:block" />
              <span className="text-lg font-bold tracking-tight sm:hidden">
                <span className="text-[var(--accent)]">FPL</span> Pulse
              </span>
            </NavLink>
            <nav className="hidden lg:flex gap-0.5" aria-label="Main navigation">
              {links.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  className={({ isActive }) =>
                    cn(
                      "rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors flex items-center gap-1.5",
                      isActive
                        ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                        : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]",
                    )
                  }
                >
                  {link.icon}
                  {link.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <NavLink
              to="/chat"
              className={({ isActive }) =>
                cn(
                  "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm font-medium transition-colors",
                  isActive
                    ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-foreground)]"
                    : "border-[var(--ai-border)] bg-[var(--ai-bg)] text-[var(--accent)] hover:opacity-90",
                )
              }
            >
              <Sparkles className="h-4 w-4" />
              <span className="hidden sm:inline">Ask Scout</span>
            </NavLink>
            <button
              onClick={() => setDark(!dark)}
              className="rounded-md p-2 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
              aria-label="Toggle dark mode"
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="lg:hidden rounded-md p-2 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              aria-expanded={menuOpen}
            >
              {menuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>
        </div>
        {menuOpen && (
          <nav className="lg:hidden border-t border-[var(--border)] bg-[var(--card)] px-6 py-3 space-y-1" aria-label="Mobile navigation">
            <NavLink
              to="/chat"
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors border",
                  isActive
                    ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-foreground)]"
                    : "border-[var(--ai-border)] bg-[var(--ai-bg)] text-[var(--accent)]",
                )
              }
            >
              <Sparkles className="h-4 w-4" />
              Ask Scout
            </NavLink>
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]",
                  )
                }
              >
                {link.icon}
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
        <span className="inline-flex items-center gap-1.5">
          <PulseLogo size={14} />
          {footerInfo
            ? `Last updated: GW${footerInfo.gameweek}, ${footerInfo.season}`
            : "Data refreshed weekly via automated pipeline"}{" "}
          &middot; Powered by Claude AI enrichment
        </span>
      </footer>
      <AskScoutDrawer />
    </div>
  );
}

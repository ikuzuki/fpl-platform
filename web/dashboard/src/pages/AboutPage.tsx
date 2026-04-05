import { ExternalLink, Mail } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PulseLogo, MetricIcons, NavIcons, StatusIcons, FdrDot, RecBadge } from "@/components/icons/FplIcons";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

const PIPELINE_STEPS = [
  {
    stage: "Collect",
    color: "var(--chart-1)",
    items: ["FPL API", "Understat xG", "News RSS"],
    tech: "Python Lambdas",
  },
  {
    stage: "Validate",
    color: "var(--chart-4)",
    items: ["Schema checks", "Dedup", "Type coercion"],
    tech: "Great Expectations",
  },
  {
    stage: "Enrich",
    color: "var(--chart-5)",
    items: ["Player summaries", "Injury signals", "Sentiment", "Fixture outlook"],
    tech: "Claude Haiku + Sonnet",
  },
  {
    stage: "Curate",
    color: "var(--chart-2)",
    items: ["FPL Score (7 components)", "Transfer picks", "Team strength", "GW briefing"],
    tech: "Python + DuckDB",
  },
  {
    stage: "Visualise",
    color: "var(--accent)",
    items: ["9 interactive pages", "Custom icon system", "URL-synced filters"],
    tech: "React + Recharts",
  },
];

const DESIGN_DECISIONS = [
  {
    title: "Chart type selection",
    body: "Scatter plots for correlation analysis (xG efficiency, ownership vs value), heatmaps for density patterns (fixture difficulty, momentum), bar charts for component breakdowns (score waterfall). Each chart type was chosen for the specific analytical question it answers — no pie charts, no decorative viz.",
  },
  {
    title: "Composite scoring",
    body: "The FPL Score blends 7 weighted signals (form, value, fixtures, xG, momentum, ICT, injury) into a single 0-100 metric. Each component is min-max normalised so different scales don't dominate. The weights were tuned against historical top-performer correlation.",
  },
  {
    title: "LLM enrichment over LangChain",
    body: "Direct Claude API calls with versioned prompts instead of a framework. Each enrichment type (summary, injury, sentiment, fixtures) uses the cheapest model that achieves the required quality — Haiku for bulk, Sonnet for nuanced reasoning. All calls traced via Langfuse.",
  },
  {
    title: "Design system tokens",
    body: "All colours defined as OKLCh CSS custom properties with automatic dark mode. Chart palette, position colours, and score component colours are referenced via var() throughout — no hardcoded hex values in component files.",
  },
  {
    title: "Accessibility baseline",
    body: "Skip-to-content link, aria-sort on sortable headers, aria-pressed on toggle buttons, labelled search inputs, keyboard-navigable expandable rows, FDR number overlays for colour-blind users. Not perfect, but deliberate.",
  },
  {
    title: "URL state sync",
    body: "All page filters (position, search, sort, metric, player selection) persist in the URL via useSearchParams. Every view is linkable and shareable — /players?pos=MID&q=salah works as expected.",
  },
];

const TECH_STACK = {
  Frontend: [
    { name: "React 19", note: "Latest hooks, strict mode" },
    { name: "TypeScript", note: "Strict, noUnusedLocals" },
    { name: "Tailwind CSS v4", note: "OKLCh design tokens" },
    { name: "Recharts", note: "Composable chart library" },
    { name: "TanStack Table", note: "Headless table state" },
    { name: "Vite 8", note: "Sub-second HMR" },
    { name: "Vitest", note: "38 tests, React Testing Library" },
  ],
  "Data Pipeline": [
    { name: "Python 3.11", note: "Type hints, Pydantic v2" },
    { name: "AWS Lambda", note: "RunHandler pattern" },
    { name: "S3 Data Lake", note: "raw → clean → enriched → curated" },
    { name: "DuckDB", note: "Local analytics engine" },
    { name: "Parquet", note: "zstd compression, Hive partitioning" },
    { name: "Great Expectations", note: "Validation at each layer" },
  ],
  "AI & Observability": [
    { name: "Claude API", note: "Haiku (bulk) + Sonnet (complex)" },
    { name: "Langfuse", note: "LLM call tracing" },
    { name: "Structured outputs", note: "Pydantic-validated JSON" },
    { name: "Versioned prompts", note: "v{N}/ directory pattern" },
  ],
  Infrastructure: [
    { name: "Terraform", note: "All resources as code" },
    { name: "AWS Step Functions", note: "Pipeline orchestration" },
    { name: "GitHub Actions", note: "CI/CD from intech-cicd" },
    { name: "eu-west-2", note: "London region" },
  ],
};

const ROADMAP = [
  { item: "Live API backend", desc: "Replace static JSON with FastAPI endpoints + cache invalidation", status: "planned" },
  { item: "Team builder", desc: "Full 15-player squad optimiser with budget constraints", status: "planned" },
  { item: "Gameweek auto-email", desc: "Weekly briefing delivered to inbox via SES", status: "planned" },
  { item: "Historical backtest", desc: "\"What if I'd followed the AI picks since GW1?\" simulation", status: "idea" },
  { item: "Live gameweek tracker", desc: "WebSocket updates during matches with live score projections", status: "idea" },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function AboutPage() {
  return (
    <div className="space-y-10">
      {/* Hero */}
      <section className="text-center py-6">
        <PulseLogo size={56} className="mx-auto mb-4" />
        <h1 className="text-3xl font-bold mb-2">FPL Pulse</h1>
        <p className="text-[var(--muted-foreground)] max-w-lg mx-auto">
          An end-to-end FPL analytics platform: automated data collection,
          LLM-powered enrichment, and an interactive dashboard for weekly
          decision-making.
        </p>
      </section>

      {/* About me */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Built by</h2>
        <Card>
          <CardContent className="pt-5">
            <div className="flex flex-col sm:flex-row items-start gap-5">
              <div className="flex-1">
                <h3 className="text-xl font-bold">Issei Kuzuki</h3>
                <p className="text-sm text-[var(--muted-foreground)] mt-1 leading-relaxed">
                  Data & software engineer building at the intersection of cloud
                  infrastructure, data pipelines, and AI-powered applications.
                  This project combines a genuine FPL obsession with a desire to
                  demonstrate full-stack depth — from Terraform modules to
                  React components, with LLM enrichment in between.
                </p>
                <div className="flex gap-3 mt-4">
                  <a
                    href="https://github.com/ikuzuki"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                  >
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .3a12 12 0 00-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.5-1.4-1.3-1.8-1.3-1.8-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-6 0-1.2.5-2.3 1.2-3.1-.1-.4-.5-1.5.1-3.2 0 0 1-.3 3.4 1.2a11.5 11.5 0 016 0c2.3-1.5 3.3-1.2 3.3-1.2.7 1.7.3 2.8.1 3.2.8.8 1.2 1.9 1.2 3.1 0 4.7-2.8 5.7-5.5 6 .4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0012 .3"/></svg>
                    GitHub
                    <ExternalLink className="h-3 w-3" />
                  </a>
                  <a
                    href="https://linkedin.com/in/ikuzuki"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                  >
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 2h-17A1.5 1.5 0 002 3.5v17A1.5 1.5 0 003.5 22h17a1.5 1.5 0 001.5-1.5v-17A1.5 1.5 0 0020.5 2zM8 19H5v-9h3zM6.5 8.25A1.75 1.75 0 118.3 6.5a1.78 1.78 0 01-1.8 1.75zM19 19h-3v-4.74c0-1.42-.6-1.93-1.38-1.93A1.74 1.74 0 0013 14.19V19h-3v-9h2.9v1.3a3.11 3.11 0 012.7-1.4c1.55 0 3.36.86 3.36 3.66z"/></svg>
                    LinkedIn
                    <ExternalLink className="h-3 w-3" />
                  </a>
                  <a
                    href="mailto:issei@example.com"
                    className="flex items-center gap-1.5 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                  >
                    <Mail className="h-4 w-4" />
                    Contact
                  </a>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Architecture pipeline */}
      <section>
        <h2 className="text-lg font-semibold mb-3">How it works</h2>
        <div className="grid gap-3 md:grid-cols-5">
          {PIPELINE_STEPS.map((step, i) => (
            <Card key={step.stage} className="relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1" style={{ backgroundColor: step.color }} />
              <CardContent className="pt-5">
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className="flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white"
                    style={{ backgroundColor: step.color }}
                  >
                    {i + 1}
                  </span>
                  <h3 className="font-semibold text-sm">{step.stage}</h3>
                </div>
                <ul className="text-xs text-[var(--muted-foreground)] space-y-1 mb-3">
                  {step.items.map((item) => (
                    <li key={item} className="flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-[var(--muted-foreground)]" />
                      {item}
                    </li>
                  ))}
                </ul>
                <Badge className="bg-[var(--muted)] text-[var(--muted-foreground)] text-[10px]">
                  {step.tech}
                </Badge>
              </CardContent>
              {i < PIPELINE_STEPS.length - 1 && (
                <div className="hidden md:block absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 z-10 text-[var(--muted-foreground)]">
                  →
                </div>
              )}
            </Card>
          ))}
        </div>
      </section>

      {/* Design decisions */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Design decisions</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {DESIGN_DECISIONS.map((d) => (
            <Card key={d.title}>
              <CardContent className="pt-4">
                <h3 className="font-semibold text-sm mb-1.5">{d.title}</h3>
                <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                  {d.body}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Icon system showcase */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Custom icon system</h2>
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-[var(--muted-foreground)] mb-4">
              23 domain-specific SVG icons built for the FPL context — replacing generic
              icon libraries with purpose-built visuals that communicate data meaning at a glance.
            </p>
            <div className="space-y-4">
              <div>
                <p className="text-[10px] text-[var(--muted-foreground)] uppercase tracking-wider mb-2">Navigation</p>
                <div className="flex gap-4 items-center flex-wrap">
                  {(["Briefing", "Players", "Fixtures", "Transfers", "Teams", "Trends"] as const).map((name) => {
                    const Icon = NavIcons[name];
                    return (
                      <div key={name} className="flex flex-col items-center gap-1">
                        <Icon size={20} className="text-[var(--foreground)]" />
                        <span className="text-[9px] text-[var(--muted-foreground)]">{name}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div>
                <p className="text-[10px] text-[var(--muted-foreground)] uppercase tracking-wider mb-2">Metrics</p>
                <div className="flex gap-4 items-center flex-wrap">
                  {(["Form", "ExpectedGoals", "Ownership", "IctIndex", "Momentum", "Value", "PriceUp", "PriceDown", "AiInsight"] as const).map((name) => {
                    const Icon = MetricIcons[name];
                    return (
                      <div key={name} className="flex flex-col items-center gap-1">
                        <Icon size={20} />
                        <span className="text-[9px] text-[var(--muted-foreground)]">{name}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div>
                <p className="text-[10px] text-[var(--muted-foreground)] uppercase tracking-wider mb-2">Status & Badges</p>
                <div className="flex gap-4 items-center flex-wrap">
                  <div className="flex flex-col items-center gap-1">
                    <StatusIcons.Available size={20} />
                    <span className="text-[9px] text-[var(--muted-foreground)]">Available</span>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <StatusIcons.Doubtful size={20} />
                    <span className="text-[9px] text-[var(--muted-foreground)]">Doubtful</span>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <StatusIcons.Injured size={20} />
                    <span className="text-[9px] text-[var(--muted-foreground)]">Injured</span>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <StatusIcons.Suspended size={20} />
                    <span className="text-[9px] text-[var(--muted-foreground)]">Suspended</span>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <StatusIcons.NewSigning size={20} />
                    <span className="text-[9px] text-[var(--muted-foreground)]">New</span>
                  </div>
                  <div className="border-l border-[var(--border)] pl-4 flex gap-2 items-center">
                    {([1, 2, 3, 4, 5] as const).map((l) => (
                      <FdrDot key={l} level={l} size={18} />
                    ))}
                  </div>
                  <div className="border-l border-[var(--border)] pl-4 flex gap-2 items-center">
                    {(["buy", "sell", "hold", "watch"] as const).map((r) => (
                      <RecBadge key={r} rec={r} size={20} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Tech stack */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Tech stack</h2>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          {Object.entries(TECH_STACK).map(([category, items]) => (
            <Card key={category}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{category}</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-2">
                  {items.map((item) => (
                    <div key={item.name} className="flex items-start justify-between gap-2">
                      <span className="text-sm font-medium">{item.name}</span>
                      <span className="text-[10px] text-[var(--muted-foreground)] text-right shrink-0">
                        {item.note}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Roadmap */}
      <section>
        <h2 className="text-lg font-semibold mb-3">What's next</h2>
        <Card>
          <CardContent className="pt-4">
            <div className="space-y-3">
              {ROADMAP.map((r) => (
                <div key={r.item} className="flex items-start gap-3">
                  <Badge
                    className={cn(
                      "shrink-0 text-[10px] mt-0.5",
                      r.status === "planned"
                        ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                        : "bg-[var(--muted)] text-[var(--muted-foreground)]",
                    )}
                  >
                    {r.status}
                  </Badge>
                  <div>
                    <p className="text-sm font-medium">{r.item}</p>
                    <p className="text-xs text-[var(--muted-foreground)]">{r.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Source */}
      <section className="text-center py-4">
        <a
          href="https://github.com/ikuzuki/fpl-platform"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .3a12 12 0 00-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.5-1.4-1.3-1.8-1.3-1.8-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-6 0-1.2.5-2.3 1.2-3.1-.1-.4-.5-1.5.1-3.2 0 0 1-.3 3.4 1.2a11.5 11.5 0 016 0c2.3-1.5 3.3-1.2 3.3-1.2.7 1.7.3 2.8.1 3.2.8.8 1.2 1.9 1.2 3.1 0 4.7-2.8 5.7-5.5 6 .4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0012 .3"/></svg>
          View source on GitHub
          <ExternalLink className="h-3 w-3" />
        </a>
      </section>
    </div>
  );
}

import { ExternalLink, Mail } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PulseLogo } from "@/components/icons/FplIcons";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

const PIPELINE_STEPS = [
  {
    stage: "Trigger",
    color: "var(--chart-3)",
    items: ["EventBridge cron", "Every Tuesday 8am UTC", "Step Functions starts"],
    tech: "EventBridge",
  },
  {
    stage: "Collect",
    color: "var(--chart-1)",
    items: ["FPL API", "Understat xG/xA", "News RSS feeds"],
    tech: "3 Lambdas in parallel",
  },
  {
    stage: "Validate",
    color: "var(--chart-4)",
    items: ["Schema checks", "Type coercion", "Invalid records to DLQ"],
    tech: "Great Expectations",
  },
  {
    stage: "Enrich",
    color: "var(--chart-5)",
    items: ["Player summaries", "Injury signals", "Sentiment", "Fixture outlook"],
    tech: "4 Lambdas in parallel",
  },
  {
    stage: "Curate",
    color: "var(--chart-2)",
    items: ["FPL Score (7 components)", "Transfer picks", "Team strength", "GW briefing"],
    tech: "Curate Lambda",
  },
];

const DESIGN_DECISIONS = [
  {
    title: "S3 data lake with 4 layers",
    adr: "ADR-0002",
    body: "One S3 bucket, four prefixes: raw (JSON, as-is from APIs), clean (Parquet, validated), enriched (Parquet, LLM-augmented), curated (Parquet, dashboard-ready). Hive-style partitioning by season and gameweek enables partition pruning and prefix-based idempotency. No separate buckets per stage - one IAM policy, one lifecycle config, one bucket to manage.",
  },
  {
    title: "Direct Anthropic SDK over LangChain",
    adr: "ADR-0003",
    body: "The enrichment pipeline makes structured batch calls: system prompt plus user message and get a JSON array back. LangChain's chain abstraction adds indirection without simplifying this pattern, pulls ~20 transitive dependencies, and wraps prompts with its own formatting. Direct SDK calls keep the Lambda container smaller, the dependency tree simpler, and debugging straightforward. LangGraph is used separately for the recommendation agent where stateful multi-step reasoning earns the framework overhead.",
  },
  {
    title: "Tiered model selection for cost control",
    adr: "ADR-0004",
    body: "Three enrichers (player summaries, injury signals, sentiment) use Haiku at $0.25/$1.25 per MTok. Fixture outlook uses Sonnet at $3/$15 per MTok because it needs to reason across 5-game sequences and team form trends. Input filtering reduces per-call token counts by 60-90% by sending only the fields each enricher's prompt actually references. Estimated cost: ~$0.72 per gameweek, ~$27 per season.",
  },
  {
    title: "Versioned prompts and Langfuse tracing",
    adr: "ADR-0005",
    body: "Prompts live in plain text files under prompts/v{N}/ directories, checked into git. Never edit a published version - create v{N+1}. Each LLM call is traced via Langfuse @observe decorators: enricher name, batch size, prompt version, token counts, latency, and a quality score for whether the LLM returned the right number of items. Session IDs group all traces for a gameweek run together.",
  },
  {
    title: "Parallel Step Functions states",
    adr: "ADR-0006",
    body: "Collectors run in parallel (3 branches, ~15s instead of ~45s sequential). Enrichers run as 4 separate Lambdas in a Parallel state - each gets its own 900s timeout, and a Sonnet failure doesn't block the Haiku enrichers. Step Functions handles per-enricher retry independently. Rate control is dual-layered: asyncio.Semaphore(2) caps in-flight connections, and a RateLimiter caps requests per minute against the model's RPM limit.",
  },
  {
    title: "Pre-generated JSON on S3 plus CloudFront",
    adr: "ADR-0007",
    body: "The curated data changes once per gameweek. The Curate Lambda writes JSON alongside its Parquet outputs to a public S3 prefix. The React app fetches static JSON files on load - no compute runs per dashboard request. Total hosting cost is around $0.50/month. When the LangGraph agent arrives in Phase 2, an API Gateway origin is added to CloudFront without touching the static dashboard at all.",
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
    { name: "AWS Lambda", note: "Container images via ECR" },
    { name: "AWS Step Functions", note: "Parallel states, retry/catch" },
    { name: "S3 Data Lake", note: "raw, clean, enriched, curated" },
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
    { name: "EventBridge", note: "Weekly pipeline trigger" },
    { name: "GitHub Actions", note: "CI/CD, path-filtered" },
    { name: "eu-west-2", note: "London region" },
  ],
};

const ROADMAP = [
  { item: "Live API backend", desc: "Replace static JSON with FastAPI endpoints and cache invalidation", status: "planned" },
  { item: "Team builder", desc: "Full 15-player squad optimiser with budget constraints", status: "planned" },
  { item: "Gameweek auto-email", desc: "Weekly briefing delivered to inbox via SES", status: "planned" },
  { item: "Historical backtest", desc: "What if I had followed the AI picks since GW1? simulation", status: "idea" },
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
                  Data and software engineer specialising in cloud
                  infrastructure, data pipelines, and AI-powered applications.
                  FPL Pulse is a full-stack personal project built end-to-end
                  with Terraform-managed AWS infrastructure, Python data
                  pipelines, and React that turned a Fantasy Premier
                  League obsession into a demonstration of production
                  engineering principles.
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
                    href="https://uk.linkedin.com/in/issei-kuzuki-ab850722b"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                  >
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 2h-17A1.5 1.5 0 002 3.5v17A1.5 1.5 0 003.5 22h17a1.5 1.5 0 001.5-1.5v-17A1.5 1.5 0 0020.5 2zM8 19H5v-9h3zM6.5 8.25A1.75 1.75 0 118.3 6.5a1.78 1.78 0 01-1.8 1.75zM19 19h-3v-4.74c0-1.42-.6-1.93-1.38-1.93A1.74 1.74 0 0013 14.19V19h-3v-9h2.9v1.3a3.11 3.11 0 012.7-1.4c1.55 0 3.36.86 3.36 3.66z"/></svg>
                    LinkedIn
                    <ExternalLink className="h-3 w-3" />
                  </a>
                  <a
                    href="mailto:ikuzuki0@gmail.com"
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
        <h2 className="text-lg font-semibold mb-1">How it works</h2>
        <p className="text-sm text-[var(--muted-foreground)] mb-3">
          Every Tuesday at 8am UTC, EventBridge fires and the pipeline runs automatically.
          No manual intervention. Data flows from three sources through validation, LLM enrichment,
          and curation before landing as static JSON served to this dashboard.
        </p>
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
            </Card>
          ))}
        </div>
      </section>

      {/* Design decisions */}
      <section>
        <h2 className="text-lg font-semibold mb-1">Design decisions</h2>
        <p className="text-sm text-[var(--muted-foreground)] mb-3">
          Each decision is documented as an Architecture Decision Record in{" "}
          <code className="text-xs bg-[var(--muted)] px-1 py-0.5 rounded">docs/adr/</code>.
          The reasoning, alternatives considered, and trade-offs are all captured there.
        </p>
        <div className="grid gap-3 md:grid-cols-2">
          {DESIGN_DECISIONS.map((d) => (
            <Card key={d.title}>
              <CardContent className="pt-4">
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <h3 className="font-semibold text-sm">{d.title}</h3>
                  <Badge className="bg-[var(--muted)] text-[var(--muted-foreground)] text-[10px] shrink-0">
                    {d.adr}
                  </Badge>
                </div>
                <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                  {d.body}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
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

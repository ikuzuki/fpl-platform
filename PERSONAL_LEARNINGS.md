# Personal Learnings

Things I've learned building FPL Platform that are genuinely non-obvious or hard-won. Organised by insight type so I can find things quickly.

---

## Gotchas — Things That Fail Silently or Behave Counter-Intuitively

### Lambda's Root Logger Defaults to WARNING
You see nothing in CloudWatch unless you explicitly reconfigure it to INFO. Every Lambda handler needs logging setup before anything else runs.

### Step Functions "Succeeded" ≠ Business Success
`LambdaFunctionSucceeded` means the invocation didn't crash — not that your business logic succeeded. A Lambda returning `{"statusCode": 500, "error": "..."}` is a "successful" invocation. This applies to both Task states and Parallel branches. You need `Choice` states checking the actual response body after every Task.

### S3 Lifecycle Rule Ordering
AWS rejects lifecycle configs where expiration days <= transition days in the same rule. Expiration must be strictly greater:
```hcl
transition { days = 30; storage_class = "STANDARD_IA" }
expiration { days = 90 }  # MUST be > transition days
```

### ECR Naming Must Match CI
If your deploy workflow constructs image names as `{project}-{service}-{env}` but your Terraform module orders it differently, pushes fail silently because the repo doesn't exist. Always trace the naming from CI → Terraform before deploying.

### Cloudflare Blocks AWS Lambda IPs
Many public APIs use Cloudflare which blocks Lambda IP ranges. User-Agent headers help with basic checks but Cloudflare also TLS-fingerprints (Python httpx ≠ Chrome). What actually works: **exponential backoff** (blocking is often temporary/rate-based) and **caching to avoid duplicate calls** within the same invocation.

### Empty LLM Responses
Under rate limit pressure, LLMs occasionally return empty content. `json.loads("")` gives the cryptic `"Expecting value: line 1 column 1 (char 0)"`. Always guard:
```python
raw_text = response.content[0].text.strip() if response.content else ""
if not raw_text:
    raise ValueError("LLM returned empty response")
```

### IAM Users Can't See Billing by Default
Even with `AdministratorAccess`, IAM users get "Access Denied" on Cost Explorer. This is an account-level setting, not IAM. Enable via root account: Account Settings → IAM User and Role Access to Billing Information → Activate.

### No Hard Spending Limits on AWS
AWS has no "stop everything at $X" switch. Closest you get: `aws_budgets_budget` with SNS notifications at 50%/80%/100% thresholds, plus CloudWatch billing alarms as backup. Requires manual intervention when alerted.

### Prompt References Must Match Input Filtering
If you filter fields before sending to the LLM (`RELEVANT_FIELDS`), updating a prompt to reference a new field means you must also add it to the filter — or the LLM simply won't see it. Silent data omission, no error.

### Corporate pip Config Leaks Into Personal Projects
If your work setup uses CodeArtifact/Artifactory, `pip install` globally routes through it — even for personal projects. Override with `--index-url https://pypi.org/simple/`.

### Windows: Notepad Silently Adds `.txt`
Saving `~/.ssh/config` via Notepad creates `config.txt` — SSH ignores it. Write config files from Git Bash instead.

### Windows: `~` Doesn't Always Resolve
`ssh-keygen -f ~/.ssh/id_ed25519` fails with "No such file or directory" on some Windows terminals. Always use the full path: `/c/Users/YourName/.ssh/id_ed25519`.

---

## Patterns — Reusable Approaches Worth Reaching For Again

### Idempotency via Output Check
Before every operation, check if the output already exists:
```python
if s3_client.list_objects(bucket, output_prefix):
    return "already processed"
```
Uses `head_object` (cheap) not `get_object`. Prevents duplicate processing on Lambda retries.

### Semaphore + Rate Limiter (Both, Not Either)
Rate limits are three things at once: RPM, output tokens per minute, AND concurrent connections. A semaphore alone doesn't prevent TPM violations. A rate limiter alone doesn't prevent connection floods. You need both:
```python
async with self.semaphore:             # max N in-flight
    await self.rate_limiter.acquire()  # max M per minute
    return await self._call_llm(batch)
```

### Prompt Enforcement vs Schema Validation
The LLM doesn't see your Pydantic model. If your prompt says `one of "positive", "negative", "neutral"` but the LLM returns `"very positive"`, Pydantic catches it — but the record is lost. Be explicit in prompts: `MUST be exactly one of these values. No other values allowed.` Pydantic is the safety net, not the instruction.

### Defensive Collection
Collect data you don't use yet if it's cheap and the API is ephemeral. Zero cost to collect, painful to backfill later if the API changes or disappears.

### Hive-Style Partitioning
Path convention like `raw/{source}/season={season}/gameweek={gw:02d}/` means tools like Athena and DuckDB can partition-prune automatically — no extra config needed.

### Zip Lambda for Infra Glue, Container for Services
Not everything needs a Docker image. For lightweight operational Lambdas (pure boto3, no shared lib), use `data "archive_file"` to zip and deploy a single file. Rule of thumb: imports your shared lib → container. Pure AWS SDK glue → zip.

### EventBridge for Pipeline Side-Effects
Post-pipeline work (cache invalidation, notifications) should be triggered by EventBridge reacting to Step Functions status changes — not added as extra steps in the pipeline. Keeps the pipeline focused on data, side-effects decoupled and independently testable. A side-effect failure doesn't fail the data pipeline.

### SSH Host Aliases for Multi-Account Git
Don't switch SSH keys manually. Create host aliases in `~/.ssh/config` and set remotes to use them:
```bash
Host github-personal
  HostName github.com
  IdentityFile /c/Users/YourName/.ssh/id_ed25519_personal
  IdentitiesOnly yes
```
Then `git remote set-url origin git@github-personal:user/repo.git`. Git picks the right key automatically.

### Terraform Bootstrap — The Chicken-and-Egg Problem
Terraform needs a state bucket, but you need Terraform to create the bucket. Solution: a separate `bootstrap/` directory applied manually once (state bucket, DynamoDB lock table, OIDC provider, CI role, budget alerts). After that, everything else uses the state bucket as backend. The bootstrap itself has no remote state.

### Log Prefixes for Parallel Execution
When multiple Lambdas or enrichers run in parallel, prefix every log line: `[ANTHROPIC]`, `[FPL API]`, `[RSS]`. Without this, CloudWatch logs from parallel executions are an unreadable interleave.

---

## Mental Models — Frameworks for Thinking

### Lambda Timeout vs Rate Limit Math
If rate limits mean your work takes 14 minutes but Lambda timeout is 15, you're one retry away from failure. Split across multiple Lambdas (each gets its own timeout) using Step Functions `Parallel` rather than squeezing everything into one.

### Collection Window ≠ Processing Window
If your pipeline runs weekly but needs a week of context, your collector must loop over last N days (idempotency skips already-collected days) and your loader must read last N days from storage. RSS feeds only hold 24-48 hours, so old data must already be persisted from previous runs.

### Cost Modelling: Work Backwards from Rate Limits, Not Pricing
Pricing tells you what it costs. Rate limits tell you if it's even possible:
```
API calls = records ÷ batch_size
Time      = API calls ÷ RPM (check output TPM too — often the real bottleneck)
Cost      = (input_tokens × price + output_tokens × price) × calls
```
The most expensive model × the most calls is always 90%+ of the cost. Optimise that one thing first.

### Serverless Infra Is Free, LLM Calls Aren't
For a weekly batch pipeline: Lambda, Step Functions, S3, Secrets Manager combined = ~$0.05/week. LLM API calls dominate. All cost optimisation should focus on model selection, batching, input filtering, and record filtering.

### Identical Timestamps = Cascading Failure
When the same error appears 10 times at the same millisecond, it's `asyncio.gather` failing multiple coroutines at once — not 10 separate failures. The root cause is the first error; the rest are consequences. Fix one thing, not ten.

### RSS Feed Quality
Feeds labelled "football" often contain boxing, cricket, etc. Always add keyword filtering on the article content, not just the feed URL. A general feed with a keyword filter outperforms a supposedly-specific feed that drifts.

### Cross-Source Name Matching
Different data sources spell names differently (accents, short names, transliterations). `unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()` to strip accents, match on full name first, fall back to short name. Accept ~75% match rate — some names are genuinely different across sources.

### Writing Good ADRs
The initial ADRs were "we chose X because it's good." What made the biggest difference:
- **Options Considered** with rejected alternatives and specific reasons — transforms an ADR from "what we did" into "how we reason about tradeoffs"
- **Dates** — without them you can't tell if they're stale
- **Ground estimates in data** — "$3/gameweek" is stronger when based on measured token counts, not vibes
- **Address hard edge cases honestly** — acknowledging a risk then hand-waving is worse than not mentioning it
- **8-10 ADRs is the sweet spot** — enough for rigour without bureaucracy. Don't ADR implementation patterns; ADRs are for choices where you genuinely had alternatives

### Path-Filtered CI in Monorepos
`dorny/paths-filter` detects which services changed and only runs their tests. The key insight: each filter must capture its full dependency chain. The `data` filter watches both `services/data/**` and `libs/**` — so a shared library change correctly triggers data service tests.

---

## Frontend Bridge — Backend-to-Frontend Concept Map

*Coming from pure backend/infra, this table was the thing that unlocked React for me.*

| React/Frontend | Python/AWS Equivalent |
|---|---|
| `package.json` | `pyproject.toml` — declares deps + scripts |
| `vite.config.ts` | `Makefile` — defines how source gets compiled |
| `node_modules/` | `venv/lib/site-packages/` |
| `dist/` | `.zip` Lambda deployment package |
| `main.tsx` | `lambda_handler()` — the first code that runs |
| `App.tsx` routes | API Gateway route table — maps URLs to page components |
| `Layout.tsx` + `<Outlet />` | Middleware wrapping handlers — nav/footer around page content |
| `pages/*.tsx` | Individual Lambda handlers — one per screen |
| `lib/types.ts` | Pydantic models (compile-time only — no runtime validation) |
| `lib/api.ts` | S3 client — fetches data |
| `components/ui/` | Utility classes in shared lib |

### `useApi` Cancellation Pattern
When a user navigates away before a fetch completes, the cleanup function sets `cancelled = true` so the callback doesn't update state on a component that no longer exists. Like checking if a Lambda invocation has been superseded before writing results.

### State Lives in Three Places
| Where | What for | Analogy |
|---|---|---|
| `useState` | Local component state (toggles, selections) | Local variable in a function |
| `useApi` | Async data + loading/error states | S3 read with try/except |
| `useSearchParams` | Filters in URL query params | API Gateway query string params |

URL state is the non-obvious win — filtered views become bookmarkable and the back button works correctly.

### OKLCH Colour Space
Perceptually uniform — `oklch(0.6 0.18 25)` and `oklch(0.6 0.18 145)` look equally "bright" to human eyes. Change the hue angle, keep lightness/chroma fixed, and palettes stay visually consistent.

---

## Workflow — What Worked for AI-Assisted Development

### Shared Working Tree = Shared Risk
Parallel agents share the same working tree. An agent switching branches silently overwrites another agent's uncommitted changes. Always commit before context-switching, and verify PR file lists after opening.

### Wave-Based Implementation
Don't try to build everything in one prompt. Structure as waves of PRs with dependencies: infra → data collectors (parallel) → processing → enrichment → orchestration → UI. Each wave can parallelise internally. Each PR = one ticket = one branch.

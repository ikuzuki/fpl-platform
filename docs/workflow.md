# Development Workflow

Practical guide for running Phase 1 development with Claude Code.

## Session Structure

Each session follows this loop:

```
make test          # confirm green base
pick one issue     # move to In Progress on board
tell Claude: "work on issue #N"
review the diff    # see checkpoints below
merge PR           # issue auto-closes via "Closes #N"
update runbook     # 5 minutes, operational notes only
```

One issue per session is a sustainable pace. Two if they're small.

## What to Personally Review (Don't Just Approve)

Three moments where you need to actually read and think:

**1. Pydantic data models**
When Claude writes the `Player`, `Fixture`, or `GameweekPick` models, open the real FPL API endpoint in your browser and compare field names directly. Claude can get these subtly wrong without live API data.

**2. Prompt templates**
Read every `v1/` prompt before it goes in. They're the creative core — Claude writes reasonable first drafts but tighten them yourself. Check: does it ask for what you actually want? Is the output schema correct?

**3. Step Functions definition**
Trace through the state machine mentally before merging. Verify that error paths (DLQ routing, retry logic) make sense for your use case, not just that they're syntactically valid.

## Parallelising with Multiple Agents

Default: **one agent per PR**. Keeps context focused and PRs clean.

OK to parallelise when two tasks are genuinely independent (no shared files):
- Terraform modules + unit tests for an existing Lambda
- Two collectors that don't share code

Don't over-parallelise — a messy PR is worse than a slow one.

## Post-Merge Runbook Updates

After each PR merges, add a section to `docs/runbook.md`:
- How to invoke the Lambda locally
- Common failure modes and how to diagnose
- How to backfill if the Lambda missed a gameweek

Claude Code can write this as a follow-up commit: "update runbook for #N".

## GitHub Project Board

Board lives at: `github.com/users/ikuzuki/projects`  
Columns: Backlog → To Do → In Progress → Review → Done

If the board is missing, create it manually:
1. Go to `github.com/ikuzuki/fpl-platform` → Projects tab
2. Link a project → New project → Board template → "FPL Platform"
3. Bulk-add existing issues via "Add item" → search by repo

## FPL Gameweek Cadence

Use the weekly gameweek deadline as a forcing function — run the pipeline end-to-end before each deadline to catch failures before they matter.

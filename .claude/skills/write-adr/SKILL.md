---
name: write-adr
description: Write an Architecture Decision Record
disable-model-invocation: true
---

Write ADR for: $ARGUMENTS

1. Find the next ADR number by listing docs/adr/ directory
2. Create docs/adr/{NNNN}-{slugified-title}.md using the template:

   # ADR-{NNNN}: {Title}

   ## Status
   Accepted

   ## Context
   {What problem are we solving?}

   ## Decision
   {What did we decide and why?}

   ## Consequences
   {What becomes easier? What becomes harder? What are the trade-offs?}

3. Keep it concise — one page max
4. Link to relevant code or other ADRs if applicable

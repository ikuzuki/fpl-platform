---
paths:
  - "services/enrich/**"
  - "services/agent/**"
---

# LLM Integration Rules
- Every LLM call must be wrapped with @observe() for Langfuse tracing
- Log input_tokens + output_tokens on every call for cost tracking
- Always include fallback handling (cache → default on API failure)
- Structured outputs must be Pydantic-validated
- Prompt templates live in prompts/v{N}/ directories, never inline
- When changing a prompt, create a new version directory (don't edit in-place)

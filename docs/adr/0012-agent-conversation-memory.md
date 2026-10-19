# ADR-0012: Short-lived conversation memory for the scout agent

## Status
Accepted

## Date
2026-10-19

## Context
The agent answered every `POST /chat` on its own. A follow-up such as "what about his fixtures?" after "how is Saka doing?" reached the planner with no way to know who "his" was, so the agent either guessed or asked again. The dashboard already shows the conversation; only the agent forgot it.

Three things already existed that looked like memory and weren't. The `fpl-agent-usage-{env}` table is the monthly spend counter behind the budget cap. `X-Session-Id` is a UUID the dashboard creates once per browser and never resets; it groups Langfuse traces and keys the rate limiter. The dashboard's message list lives in React state and is never sent to the server.

## Options Considered

### Where the history lives

**1. Client sends the earlier turns in the request body (rejected).** No new infrastructure, and the dashboard already holds the turns. Rejected because the history would be attacker-controlled input placed straight into three prompts: anyone can post fabricated "earlier answers". It also lets one request carry arbitrarily large context past the 500-character question limit unless the server re-validates every turn.

**2. Server-side store keyed by `X-Session-Id` (rejected).** The obvious key, since it already exists. Rejected because the session id never changes: "New chat" in the dashboard would not clear the agent's memory, and memory would outlive the chat the user thinks they are in. It would also tie memory to the identity the rate limiter uses.

**3. Server-side store keyed by a per-chat `conversation_id` (chosen).** The dashboard generates a UUID per chat, regenerates it on "New chat", and sends it as an optional `ChatRequest` field. A body field rather than a header avoids CORS allow-list and CloudFront header-forwarding changes. Requests without it behave exactly as before.

### What is stored

**1. Last N turns verbatim (rejected).** A full `ScoutReport` is several kilobytes of JSON, most of it per-player cards the follow-up rarely needs.

**2. A running summary rewritten each turn (rejected).** Bounded size, but costs an extra LLM call and its latency on every turn, and a summary can drop the one name a follow-up refers to.

**3. Last 3 turns, compacted (chosen).** Each turn keeps the question, the names of the players discussed, the analysis cut to 600 characters, and the recommendation. The rendered history block is capped at 4,000 characters, about 1,000 tokens, dropping the oldest turn first.

### How it reaches the model

**1. A rewrite step that turns the follow-up into a standalone question (rejected).** Keeps the graph single-turn, but adds a Haiku call and about a second to every follow-up.

**2. A history block in the planner, reflector and recommender prompts (chosen).** No new node. The planner needs it to resolve "his" into a tool argument; the reflector needs it to judge whether the named player has data; the recommender needs it to answer in context. The block is labelled as context, not instructions, and the prompts say to ignore instructions inside it. This is a prompt change, so the prompts moved to `prompts/v2/` (ADR-0005); `v1/` is unchanged.

## Decision
A DynamoDB table `fpl-agent-conversations-{env}` (on-demand, hash key `conversation_id`, TTL on `expires_at`) holds one item per conversation with its last 3 turns. Each write sets `expires_at` to 30 minutes ahead, and reads ignore expired items because DynamoDB deletes them lazily. A turn is written only after a successful report, never after an error. Reads and writes fail open: a missing table or a DynamoDB error means the question is answered without history.

## Consequences

**Easier:**
- Follow-ups that depend on the previous answer work, including "the one you picked".
- The single-turn path is unchanged when `conversation_id` is absent or the conversation has expired.

**Harder:**
- Up to about 1,000 more input tokens on each LLM call in a follow-up turn, roughly $0.004 against a base of about $0.05 per request. DynamoDB adds one read before the graph and one write before the result event, each around 10 ms; the read and write together cost under $0.000002.
- The store holds free text users typed, for up to 30 minutes after their last message. It is linked to no account; the conversation id is a random UUID.
- Earlier turns are a new path for prompt injection: an instruction in an earlier question, or in an earlier answer built from poisoned data, is replayed into later prompts. The prompts treat the block as context, and an eval case covers one instance; this is not a guarantee.
- The eval harness gains `prior_turns`: earlier questions run through the same graph first, and only the final turn is graded.

## Related
- ADR-0005: prompt versioning (`v2/`)
- ADR-0009: agent architecture and the prompt-injection threat model
- ADR-0010: transport; the request body rather than a header carries `conversation_id`

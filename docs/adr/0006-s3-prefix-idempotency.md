# ADR-0006: S3 Prefix-Based Idempotency

## Status
Accepted

## Date
2026-04-04

## Context
Data collectors and transformers are invoked by Step Functions, which retries on failure. Without idempotency, retries produce duplicate files in S3. We needed a mechanism to detect "already done" and skip re-processing.

## Options Considered

### 1. DynamoDB state table (rejected)
Write a completion record on success, check before starting. Schema: `{season, gameweek, stage, status, timestamp}`.

**Rejected because:** Adds a DynamoDB table to manage, introduces eventual consistency between S3 and the state table, and requires cleanup/TTL logic. The state table would duplicate information already implicit in S3 (if the file exists, the work is done).

### 2. Lambda destination deduplication (rejected)
Use Lambda request IDs or idempotency tokens to prevent re-execution.

**Rejected because:** Only prevents exact duplicate invocations, not logical duplicates (same gameweek, different invocation). Doesn't help with "was this gameweek already collected?" checks.

### 3. S3 prefix existence check (chosen)
Call `s3_client.list_objects(bucket, prefix)` before each operation — if files exist under the output prefix, skip.

## Decision
Use S3 prefix existence checks for idempotency. Before each collect/transform operation, check if output already exists. A `force=True` parameter overrides the check for backfills.

```python
if not force and self._output_exists(prefix):
    return CollectionResponse(status="success", records_collected=0, output_path=prefix)
```

## Partial write mitigation
Each collector writes a **single JSON file per invocation** (e.g., one `bootstrap/{timestamp}.json`). S3 `PutObject` is atomic — the object either fully exists or doesn't. There is no scenario where a collector writes 3 of 4 files because each method produces exactly one output file.

If the Lambda crashes *before* the `PutObject` call, no file is written and the next retry correctly sees an empty prefix. If it crashes *after*, the file exists and the retry correctly skips.

The `force=True` parameter exists for backfills and manual re-processing, not as a mitigation for partial writes.

## Consequences
**Easier:**
- No additional infrastructure — S3 is already the data store and source of truth
- Hive-style partitioning (`season={s}/gameweek={gw}/`) makes prefix checks natural
- Simple to reason about: "data exists at prefix = work is done"
- `list_objects` is cheap (~$0.005 per 1,000 requests) and fast (~50-100ms)

**Harder:**
- If the output format changes (e.g., collector starts writing multiple files), the single-file atomicity assumption breaks — would need to revisit
- `list_objects` adds latency per check — acceptable for batch Lambda, not suitable for real-time
- No locking — two concurrent invocations could both see "empty" and both write. Acceptable because our Step Functions pipeline is sequential, not parallel

# ADR-0006: S3 Prefix-Based Idempotency

## Status
Accepted

## Context
Data collectors and transformers are invoked by Step Functions, which retries on failure. Without idempotency, retries produce duplicate files in S3. We needed a mechanism to detect "already done" and skip re-processing.

Options considered:
1. **DynamoDB state table** — write a record on completion, check before starting
2. **S3 prefix existence check** — list objects under the output prefix, skip if non-empty
3. **Lambda destination deduplication** — use request IDs to prevent re-execution

## Decision
Use S3 prefix existence checks. Before each collect/transform operation, call `s3_client.list_objects(bucket, prefix)` — if files exist, return early with `records_collected=0`.

```python
if not force and self._output_exists(prefix):
    return CollectionResponse(status="success", records_collected=0, output_path=prefix)
```

A `force=True` parameter overrides the check for backfills.

## Consequences
**Easier:**
- No additional infrastructure — S3 is already the data store
- S3 is the single source of truth: if the file is there, the work is done
- Hive-style partitioning (`season={s}/gameweek={gw}/`) makes prefix checks natural
- Simple to reason about: "data exists = done"
- `force=True` provides an escape hatch for re-processing

**Harder:**
- Partial writes: if a collector writes 3 of 4 files and fails, the prefix check sees it as "done" — the `force` flag handles this but requires manual intervention
- `list_objects` adds latency (~50-100ms) per check — acceptable for our Lambda execution model
- Not suitable for high-concurrency scenarios (no locking) — fine for our scheduled, sequential pipeline

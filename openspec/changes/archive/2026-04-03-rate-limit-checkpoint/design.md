## Context

nanobot's agent loop (`AgentRunner.run()` in `runner.py`) calls LLM providers via `chat_with_retry()` / `chat_stream_with_retry()` in `base.py`. When a provider returns a 429 or quota error, the retry logic in `_run_with_retry()` attempts up to 3 retries (standard mode) or 10 identical errors (persistent mode) before giving up. The error surfaces as `AgentRunResult(stop_reason="error")` and is treated identically to any other LLM failure — saved as a normal turn in session history, error message returned to the user.

The existing runtime checkpoint system (`_set_runtime_checkpoint` / `_restore_runtime_checkpoint`) saves mid-flight tool-call state for crash recovery. It's the wrong abstraction for rate-limit recovery because it tracks partial tool execution state, not "retry this entire message later."

## Goals / Non-Goals

**Goals:**
- Detect when the LLM provider returns a terminal rate-limit error (retries exhausted)
- Save a lightweight checkpoint so the user's original message can be replayed later
- On startup, proactively resume all pending checkpoints and deliver results to channels
- Support both CLI (`nanobot agent`) and gateway (`nanobot gateway`) modes
- Expire stale checkpoints after 2 weeks

**Non-Goals:**
- Partial tool-chain recovery (we replay the whole message from scratch)
- Automatic retry scheduling (no timers or background polling — resume only on startup)
- Distinguishing between rate limit types (429 vs quota — treated uniformly)
- Modifying the existing runtime checkpoint system (separate mechanism)

## Decisions

### 1. Detection: classify errors in `AgentRunner`

Add a `is_rate_limited: bool` field to `AgentRunResult`. In `AgentRunner.run()`, when `stop_reason == "error"`, check if the error content matches rate-limit markers (reuse `_TRANSIENT_ERROR_MARKERS` from `base.py`, specifically the 429/rate-limit subset). This keeps classification close to the error source and avoids scattering detection logic across layers.

Rationale: The runner already sees the final error content. Adding a boolean flag is minimally invasive and doesn't change the existing error handling path for non-rate-limit errors.

### 2. Checkpoint storage: session metadata

Store checkpoints in `session.metadata["rate_limit_checkpoint"]` — a single dict. This leverages the existing `SessionManager` persistence (JSONL) and avoids new files or database tables.

Checkpoint schema:
```python
{
    "original_message": str,       # user's message text
    "media": list | None,          # media attachments if any
    "timestamp": str,              # ISO 8601
    "channel": str,                # e.g. "telegram", "cli"
    "chat_id": str,                # channel-specific chat ID
    "session_key": str,            # e.g. "telegram:123456"
    "error_summary": str,          # short human-readable summary
}
```

One checkpoint per session. If a new rate-limit error hits the same session, it overwrites the previous checkpoint (the earlier task's context is already in session history).

### 3. Save flow: intercept in `_process_message()`

In `loop.py:_process_message()`, after `_run_agent_loop()` returns, check if the result indicates rate limit. If so:
1. Save checkpoint to session metadata
2. Do NOT call `_save_turn()` — the error should not appear in conversation history
3. Send a notification to the channel: "Rate limit hit — I'll pick this up when I'm back."
4. Return the notification as the outbound message

Rationale: `_process_message()` is the single point where sessions, channels, and the bus converge. It's the natural place to decide "save checkpoint instead of normal turn."

### 4. Resume flow: scan on startup in `loop.run()`

Add `_resume_rate_limit_checkpoints()` called at the beginning of `loop.run()`, after MCP connection but before the main `while self._running` loop. This method:

1. Calls `sessions.scan_metadata("rate_limit_checkpoint")` to find all sessions with pending checkpoints
2. For each checkpoint:
   - Check TTL (2 weeks from `timestamp`) — expire and delete if stale
   - Publish a proactive notification to the channel: "Back online — resuming your earlier task..."
   - Construct a synthetic `InboundMessage` from the checkpoint data
   - Call `_dispatch(msg)` to process it through the normal agent loop
3. Clear the checkpoint from session metadata

Rationale: Running before the main loop means channels are already connected (gateway subscribed, CLI ready). Using `_dispatch()` ensures per-session serialization and concurrency gating. The resume is just a "message from the past" flowing through the normal pipeline.

### 5. Discovery: add `scan_metadata()` to `SessionManager`

Add a method to `SessionManager` that scans session files for a given metadata key without loading full histories. This avoids loading all sessions into memory on startup.

Implementation: Read the metadata line (first line of each `.jsonl` file) and check for the key. Return a list of `(session_key, checkpoint_data)` tuples.

### 6. Rate-limit marker reuse

Extract a dedicated `_RATE_LIMIT_MARKERS` tuple from the existing `_TRANSIENT_ERROR_MARKERS` in `base.py`, containing only 429-specific markers (`"429"`, `"rate limit"`, `"quota"`). Add a classmethod `is_rate_limit_error(content: str) -> bool` to `LLMProvider`.

Rationale: `_TRANSIENT_ERROR_MARKERS` includes 500s, timeouts, and connection errors — those are transient but not rate-limit. We need a stricter set for checkpoint-worthy errors.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| **Resume fires on every gateway restart** — if gateway restarts frequently, users get spammed with "resuming" messages | Only resume if checkpoint exists (one-shot). After resume, checkpoint is cleared. No repeated notifications. |
| **Channel disconnected at resume time** — outbound publish fails silently | Task still runs; result is saved to session history. User sees it next time they message. |
| **Rate limit hits again on resume** — burns through quota on startup | The resume goes through normal retry flow. If it rate-limits again, a new checkpoint is saved. Converges naturally — won't loop more than once per startup. |
| **Multiple sessions with checkpoints** — all resume concurrently on startup | `_concurrency_gate` (asyncio.Semaphore, default 3) already limits parallel sessions. No change needed. |
| **CLI resume before interactive prompt** — user might not expect it | Resume runs before the first prompt. User sees "Resuming your earlier task..." then the result. Natural flow. |

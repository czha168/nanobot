## Why

When the LLM provider returns a rate limit or quota error (429, usage quota exceeded), nanobot retries a few times then gives up. The user's message is lost — they must manually re-send it later. For gateway users (Telegram, Discord, etc.), the experience is worse: the bot goes silent and the user doesn't know if it's temporary or broken. There is no mechanism to recover from rate limit exhaustion across restarts.

## What Changes

- **Rate limit detection**: Classify LLM errors as rate-limit vs other errors at the runner level, distinguishing transient retries from terminal quota exhaustion.
- **Checkpoint save**: When rate limit is terminal (retries exhausted), save a lightweight checkpoint to session metadata containing the original user message, channel routing info, and timestamp. Do NOT save the error as a normal conversation turn.
- **Proactive resume on startup**: When `nanobot gateway` or `nanobot agent` starts, scan for pending rate-limit checkpoints across all sessions. For each valid (non-expired) checkpoint, proactively notify the channel and replay the original message through the normal agent loop.
- **TTL expiry**: Checkpoints expire after 2 weeks. Expired checkpoints are silently deleted during the resume scan.
- **Notification**: On save, notify the user via the channel that a checkpoint was saved. On resume, notify that the task is being resumed.

## Capabilities

### New Capabilities
- `rate-limit-checkpoint`: Detects terminal rate-limit errors, saves a recovery checkpoint to session metadata, and resumes pending tasks on next startup.

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- **nanobot/agent/runner.py**: Add `is_rate_limited` flag to `AgentRunResult`. Classify error responses using existing `_TRANSIENT_ERROR_MARKERS`.
- **nanobot/agent/loop.py**: Save rate-limit checkpoint on detection. Add `_resume_rate_limit_checkpoints()` called at startup before the main loop. Skip `_save_turn()` for rate-limited errors.
- **nanobot/session/manager.py**: Add `scan_metadata()` to discover sessions with pending checkpoints without loading all session histories.
- **nanobot/providers/base.py**: Expose rate-limit classification as a reusable method (markers already exist in `_TRANSIENT_ERROR_MARKERS`).
- **Tests**: New tests in `tests/agent/` for save, resume, expiry, and edge cases.

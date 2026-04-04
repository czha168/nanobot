## 1. Rate-limit error classification

- [x] 1.1 Add `_RATE_LIMIT_MARKERS` tuple to `nanobot/providers/base.py` containing `"429"`, `"rate limit"`, `"quota"`, `"resource exhausted"`. Add classmethod `is_rate_limit_error(content: str) -> bool` to `LLMProvider`.
- [x] 1.2 Add `is_rate_limited: bool = False` field to `AgentRunResult` dataclass in `nanobot/agent/runner.py`.
- [x] 1.3 In `AgentRunner.run()`, after the main loop, when `stop_reason == "error"` and `final_content` is set, call `LLMProvider.is_rate_limit_error(final_content)`. If true, set `result.is_rate_limited = True` and `result.stop_reason = "rate_limited"`.

## 2. Checkpoint save on rate limit

- [x] 2.1 Define `_RATE_LIMIT_CHECKPOINT_KEY = "rate_limit_checkpoint"` constant on `AgentLoop` in `nanobot/agent/loop.py`.
- [x] 2.2 In `_process_message()`, after `_run_agent_loop()` returns, check if the runner result indicates rate limit. If so: (a) save checkpoint to `session.metadata[_RATE_LIMIT_CHECKPOINT_KEY]` with original message, media, timestamp, channel, chat_id, session_key, and error summary; (b) call `self.sessions.save(session)`; (c) skip `_save_turn()`; (d) send notification to channel; (e) return notification as outbound message. Do NOT clear the runtime checkpoint or save the error as a normal turn.
- [x] 2.3 Return `None` from `_run_agent_loop()` needs to propagate the `is_rate_limited` flag. Change return type to include a flag or check via the runner result directly in `_process_message()`. Simplest: have `_run_agent_loop()` return a named tuple or add the flag as a fourth element in the return tuple.

## 3. Session metadata scanning

- [x] 3.1 Add `scan_metadata(key: str) -> list[tuple[str, dict]]` method to `SessionManager` in `nanobot/session/manager.py`. This method reads the metadata line (first JSONL line with `_type == "metadata"`) from each session file and returns `(session_key, metadata_value)` pairs where the key exists. Do not load full session histories.

## 4. Proactive resume on startup

- [x] 4.1 Add `_resume_rate_limit_checkpoints()` async method to `AgentLoop`. This method: (a) calls `self.sessions.scan_metadata(_RATE_LIMIT_CHECKPOINT_KEY)`; (b) for each result, checks if `timestamp` is within 2 week; (c) if expired, deletes the checkpoint and skips; (d) if valid, publishes a proactive notification to the channel; (e) constructs a synthetic `InboundMessage` from checkpoint data; (f) calls `_dispatch(msg)` to process through the normal pipeline; (g) clears the checkpoint from session metadata after dispatch.
- [x] 4.2 Call `await self._resume_rate_limit_checkpoints()` in `AgentLoop.run()` after `await self._connect_mcp()` but before the `while self._running` loop.
- [x] 4.3 For CLI mode: ensure `process_direct()` or the interactive REPL also checks for pending checkpoints before processing user input. The simplest path: `run()` handles it for gateway; for CLI, the checkpoint scan runs when the loop starts (which covers interactive mode). For one-shot mode (`nanobot agent -m`), add the scan before processing the `-m` message.

## 5. Tests

- [x] 5.1 Test rate-limit error classification: verify `is_rate_limit_error()` returns `True` for 429/quota/rate-limit content and `False` for 500/timeout/connection errors.
- [x] 5.2 Test `AgentRunResult.is_rate_limited` is set correctly when runner encounters rate-limit vs non-rate-limit errors (mock provider).
- [x] 5.3 Test checkpoint save: verify session metadata contains `rate_limit_checkpoint` after rate-limited response, and that `_save_turn()` is NOT called.
- [x] 5.4 Test checkpoint resume: verify pending checkpoint is discovered by `scan_metadata()`, replayed, and cleared from metadata.
- [x] 5.5 Test TTL expiry: verify checkpoint older than 2 weeks is deleted without replay.
- [x] 5.6 Test non-rate-limit errors: verify no checkpoint is saved for 500/timeout errors (existing behavior preserved).

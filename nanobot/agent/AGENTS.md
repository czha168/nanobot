# Agent Module

Core LLM↔tool loop, prompt assembly, memory, skills, and subagent management.

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Change the agent loop | `loop.py` | `AgentLoop` — ~800 lines, handles LLM↔tool cycle, streaming, checkpoints |
| Change system prompt | `context.py` | Assembles prompt from templates, memory, runtime info, tools |
| Add lifecycle hooks | `hook.py` | `AgentHook` — before_execute_tools, on_stream, on_stream_end, after_iteration, finalize_content |
| Change memory behavior | `memory.py` | Consolidation on session close |
| Add/modify agent tools | `tools/` | See `tools/AGENTS.md` |
| Background task spawning | `subagent.py` | Subagent executor |
| Skill loading | `skills.py` | Discovers and loads SKILL.md from skills/ dirs |
| Agent turn execution | `runner.py` | Retry logic, turn management |

## CONVENTIONS

- **Tool registration**: Tools registered in `AgentLoop._register_default_tools()` — NOT auto-discovered. Add tool class, then register explicitly.
- **Streaming**: `_LoopHook` bridges `AgentHook.on_stream()` / `on_stream_end()` to channel delivery. Multiple hooks chain via `_LoopHookChain`.
- **Checkpoint/resume**: `_restore_runtime_checkpoint()` saves tool-call state mid-flight for long tasks. Checkpoint stored in session metadata.
- **Context window**: Managed by `context_block_limit` and `context_window_tokens`. Sanitizes persisted blocks via `_sanitize_persisted_blocks()`.
- **Concurrency**: `_concurrency_gate` (asyncio.Semaphore) limits parallel sessions. `_session_locks` per session key.

## ANTI-PATTERNS

- **DO NOT** add tools via auto-discovery — always register in `_register_default_tools()`.
- **DO NOT** bypass the hook chain — use `AgentHook` interface for all lifecycle events.
- **DO NOT** manipulate session history directly — use `_save_turn()` and `_sanitize_persisted_blocks()`.

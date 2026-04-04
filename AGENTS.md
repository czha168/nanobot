# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-03
**Commit:** 7113ad3
**Branch:** main

## OVERVIEW

nanobot — ultra-lightweight personal AI assistant framework. Python 3.11+, async (asyncio), Typer CLI, Pydantic config. Multi-channel (Telegram, Discord, Slack, WhatsApp, Feishu, etc.), multi-provider (OpenRouter, Anthropic, OpenAI, DeepSeek, Ollama, etc.), MCP support.

## STRUCTURE

```
nanobot/
├── nanobot/            # Source package
│   ├── agent/          # Core agent loop, tools, context, memory, skills, subagents
│   ├── channels/       # 12 chat channel integrations (plugin system)
│   ├── providers/      # LLM provider backends + registry
│   ├── bus/            # Internal async message bus
│   ├── config/         # Pydantic config schema
│   ├── session/        # Conversation history persistence
│   ├── cron/           # Scheduled task engine
│   ├── heartbeat/      # Periodic proactive wake-up
│   ├── command/        # Slash-command router
│   ├── security/       # Network access control
│   ├── skills/         # Bundled skills (github, weather, tmux, etc.)
│   ├── templates/      # Agent prompt templates (AGENTS.md, MEMORY.md, etc.)
│   ├── cli/            # Typer CLI commands
│   ├── api/            # OpenAI-compatible HTTP API server
│   ├── utils/          # Shared utilities
│   └── nanobot.py      # Nanobot facade class (SDK entry)
├── bridge/             # WhatsApp Node.js bridge
├── tests/              # pytest suite (mirrors nanobot/ structure)
├── docs/               # Channel plugin guide, Python SDK docs
└── case/               # Demo GIFs for README
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add a new LLM provider | `nanobot/providers/registry.py` + `nanobot/config/schema.py` | 2-step: ProviderSpec + ProvidersConfig field |
| Add a new chat channel | `nanobot/channels/` | Plugin system — see `docs/CHANNEL_PLUGIN_GUIDE.md` |
| Add a new agent tool | `nanobot/agent/tools/` | Register in `AgentLoop._register_default_tools()` |
| Modify agent loop behavior | `nanobot/agent/loop.py` | AgentLoop class — the core LLM↔tool cycle |
| Change prompt construction | `nanobot/agent/context.py` | System prompt builder |
| Change memory behavior | `nanobot/agent/memory.py` | Persistent memory consolidation |
| Add a CLI command | `nanobot/cli/commands.py` | Typer app — `app` is the root |
| Change config schema | `nanobot/config/schema.py` | Pydantic BaseModel |
| Add scheduled task logic | `nanobot/cron/` | Cron engine + store |
| Add a bundled skill | `nanobot/skills/<name>/` | Skill dir with SKILL.md + optional scripts/ |
| Heartbeat/periodic tasks | `nanobot/heartbeat/service.py` | Checks HEARTBEAT.md on interval |
| Message routing | `nanobot/bus/` | Internal async pub/sub bus |
| Session history | `nanobot/session/` | JSONL per session key |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `Nanobot` | Class | `nanobot/nanobot.py` | SDK facade — `from_config()`, `run()`, `RunResult` |
| `AgentLoop` | Class | `nanobot/agent/loop.py` | Core LLM↔tool loop, session mgmt, streaming |
| `AgentHook` | Class | `nanobot/agent/hook.py` | Lifecycle hook interface (before_execute_tools, etc.) |
| `app` | Typer | `nanobot/cli/commands.py` | CLI entry — agent, gateway, serve, onboard, status |
| `PROVIDERS` | Dict | `nanobot/providers/registry.py` | ProviderSpec registry — single source of truth |
| `BaseChannel` | Class | `nanobot/channels/base.py` | Channel plugin base class |
| `Bus` | Class | `nanobot/bus/` | Async message bus for inbound/outbound |
| `_make_provider` | Func | `nanobot/cli/commands.py:378` | Provider factory from config+model |

## CONVENTIONS

- **Async everywhere**: All I/O is `async def`. pytest uses `asyncio_mode = "auto"`.
- **Pydantic config**: `~/.nanobot/config.json` → `ProvidersConfig` / `AgentsConfig` etc. All config via Pydantic models.
- **Registry pattern**: Providers (`registry.py`) and channels (`registry.py`) use dict-based registries, not if-elif chains.
- **Typer CLI**: `app = typer.Typer()` with subcommands. Entry: `nanobot.cli.commands:app` in pyproject.toml.
- **Logging**: `loguru` — not stdlib logging.
- **Line length**: 100 chars (ruff, E501 ignored).
- **Branching**: `main` = stable, `nightly` = experimental. Target `nightly` for new features.

## ANTI-PATTERNS (THIS PROJECT)

- **DO NOT use `litellm`** — removed since v0.1.4.post6 due to supply chain poisoning. Use native `openai` + `anthropic` SDKs.
- **DO NOT add if-elif chains for providers** — use `ProviderSpec` registry in `nanobot/providers/registry.py`.
- **DO NOT add if-elif chains for channels** — use channel plugin system + `registry.py`.
- **DO NOT modify `HEARTBEAT.md` directly for reminders** — use the `cron` tool for scheduled notifications.
- **Empty `allowFrom` denies all access** (since v0.1.4.post4) — use `["*"]` to allow everyone.
- **DO NOT suppress errors with bare `except:`** — always catch specific exceptions.

## UNIQUE STYLES

- **Provider = 2 files**: Add `ProviderSpec` to `registry.py` + field to `ProvidersConfig` in `schema.py`. No other files needed.
- **Channel = plugin**: Subclass `BaseChannel`, register in `registry.py`, enable in config. No core modifications.
- **Agent tools = registered methods**: Tools are registered in `_register_default_tools()`, not auto-discovered.
- **Session = JSONL**: One `.jsonl` file per session key, stored in workspace.
- **Streaming via hooks**: `AgentHook.on_stream()` / `on_stream_end()` for real-time token delivery to channels.
- **Checkpoint/resume**: Runtime checkpoint system for long-running agent tasks (see `_restore_runtime_checkpoint`).
- **WhatsApp bridge**: Separate Node.js process in `bridge/`, communicated via WebSocket.

## COMMANDS

```bash
# Development
pip install -e ".[dev]"           # Install with dev deps
nanobot onboard --wizard          # Interactive setup

# Testing
pytest                            # Run all tests (asyncio auto mode)
pytest tests/agent/               # Run agent tests only
pytest --cov=nanobot              # With coverage

# Linting
ruff check nanobot/               # Lint
ruff format nanobot/              # Format

# Running
nanobot agent                     # Interactive CLI chat
nanobot agent -m "Hello!"         # One-shot message
nanobot gateway                   # Start multi-channel gateway
nanobot serve                     # OpenAI-compatible API server
nanobot status                    # Show config/provider status
```

## NOTES

- Config lives at `~/.nanobot/config.json`, workspace at `~/.nanobot/workspace/`.
- Each channel integration has its own login flow (e.g., `nanobot channels login whatsapp`).
- MCP servers configured in `tools.mcpServers` in config — stdio or HTTP transport.
- Multi-instance support via `--config` flag with separate config/workspace dirs.
- The `bridge/` dir is a Node.js app for WhatsApp — bundled into the wheel via hatch config.
- Tests mirror source structure: `tests/agent/`, `tests/channels/`, etc.
- Security: `restrictToWorkspace` sandboxes all file/shell operations.
- `nanobot/templates/AGENTS.md` is the runtime agent system prompt (NOT this file).

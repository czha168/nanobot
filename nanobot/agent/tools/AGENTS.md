# Agent Tools

Built-in tools for the agent loop. Each tool is a class registered in `AgentLoop._register_default_tools()`.

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add a new tool | New file + register in `loop.py` | Subclass `BaseTool`, add to `_register_default_tools()` |
| File operations | `filesystem.py` | read_file, write_file, edit_file, list_directory |
| Shell commands | `shell.py` | exec — with restrictToWorkspace sandbox |
| Web search/fetch | `web.py` | web_search + web_fetch (brave, tavily, jina, searxng, duckduckgo) |
| Send messages | `message.py` | Send text to channels |
| Scheduled tasks | `cron.py` | create/list/remove cron jobs |
| External tools | `mcp.py` | Bridges MCP server tools as native agent tools |
| Background tasks | `spawn.py` | Subagent spawn for parallel execution |
| Tool base class | `base.py` | Defines name, description, schema, execute() |
| Tool registry | `registry.py` | Stores tool instances by name |

## CONVENTIONS

- **Registration**: Tools registered explicitly in `_register_default_tools()`. NOT auto-discovered from directory.
- **BaseTool interface**: `name`, `description`, `schema` (JSON Schema), `execute(**kwargs)`.
- **Sandbox**: When `restrict_to_workspace=True`, filesystem and shell tools are path-constrained.
- **MCP bridging**: MCP tools get `mcp_{server}_{tool}` naming. `enabledTools` config filters which MCP tools to register.
- **Tool timeout**: Default 30s per call. Override via `toolTimeout` in MCP server config.
- **Web proxy**: `tools.web.proxy` routes all search+fetch through a configurable proxy.

## ANTI-PATTERNS

- **DO NOT** auto-discover tools — always register explicitly.
- **DO NOT** bypass the tool schema — LLM generates args from JSON Schema.
- **DO NOT** execute shell commands without sandbox checks when `restrict_to_workspace` is enabled.

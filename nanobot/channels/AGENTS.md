# Channels Module

12+ chat platform integrations via plugin system. Each channel is a self-contained module subclassing `BaseChannel`.

## STRUCTURE

```
channels/
├── base.py        # BaseChannel — abstract interface
├── manager.py     # Lifecycle (start/stop all enabled channels)
├── registry.py    # Dict-based channel registry
└── {channel}.py   # One file per channel
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add a new channel | New `{name}.py` + `registry.py` | Subclass BaseChannel, add to registry |
| Change channel base behavior | `base.py` | Defines start/stop/send/receive interface |
| Channel lifecycle | `manager.py` | Starts/stops all enabled channels, routes messages |
| Channel registration | `registry.py` | Dict-based — NOT if-elif |
| Channel login flow | `cli/commands.py` | `channels_login()` dispatches to channel.login() |

## CONVENTIONS

- **Plugin pattern**: Each channel = one .py file, self-contained. Subclass `BaseChannel`, add to `registry.py`.
- **Group policies**: `"mention"` (default, respond only when @mentioned), `"open"` (all messages), `"allowlist"` (specific groups).
- **Access control**: `allowFrom` — empty `[]` denies all (since v0.1.4.post4). Use `["*"]` for open access.
- **Transport**: Most channels use WebSocket or long-polling (no public IP needed). WhatsApp uses separate Node.js bridge.
- **Login**: Interactive via `nanobot channels login <channel>`. WhatsApp/WeChat use QR code, others use token/credentials.
- **Streaming**: Channels receive streaming deltas via `_LoopHook.on_stream()` and render progressively.

## ANTI-PATTERNS

- **DO NOT** add if-elif chains for channels — use registry dict.
- **DO NOT** hardcode channel configs — all settings via `~/.nanobot/config.json`.
- **DO NOT** block the event loop in channel handlers — all I/O must be async.

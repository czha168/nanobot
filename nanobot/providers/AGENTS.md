# Providers Module

LLM provider backends. Registry-based — adding a provider = 2 files, no if-elif chains.

## STRUCTURE

```
providers/
├── registry.py               # PROVIDERS dict — ProviderSpec for each provider
├── base.py                   # Base provider interface
├── openai_compat_provider.py # Generic OpenAI-compatible (most providers use this)
├── anthropic_provider.py     # Anthropic-specific (different API shape)
├── azure_openai_provider.py  # Azure OpenAI (different auth)
├── openai_codex_provider.py  # Codex (OAuth token refresh)
├── github_copilot_provider.py # Copilot (OAuth token refresh)
├── transcription.py          # Whisper voice transcription via Groq
└── openai_responses/         # OpenAI Responses API submodule
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add a new provider | `registry.py` + `config/schema.py` | 2 steps: ProviderSpec entry + ProvidersConfig field |
| Change provider matching | `registry.py` | Auto-matches model names to providers via `keywords` |
| Change a specific provider | `{provider}.py` | Most use `openai_compat_provider` — only Anthropic/Azure need custom |
| Add OAuth provider | See `openai_codex_provider.py` | Token refresh + session storage pattern |
| Voice transcription | `transcription.py` | Whisper API via Groq provider |
| ProviderSpec options | `registry.py` | is_gateway, model_overrides, env_extras, detect_by_key_prefix, etc. |

## CONVENTIONS

- **ProviderSpec fields**: `name`, `keywords` (for model→provider matching), `env_key`, `display_name`, `default_api_base`, `is_gateway`, `model_overrides`, `detect_by_key_prefix`, `strip_model_prefix`, `supports_max_completion_tokens`.
- **Gateway providers** (OpenRouter, AiHubMix): Set `is_gateway=True`. Can route any model. Matched by API key prefix or base URL keyword.
- **Default provider**: `openai_compat_provider` handles any OpenAI-compatible API. Only add a custom provider if the API shape differs.
- **Config field**: Every `ProviderSpec.name` must have a matching field in `ProvidersConfig` (schema.py).

## ANTI-PATTERNS

- **DO NOT** use `litellm` — removed since v0.1.4.post6 (supply chain poisoning).
- **DO NOT** add if-elif chains — always use registry lookup.
- **DO NOT** hardcode API keys — use `env_key` for environment variable fallback.
